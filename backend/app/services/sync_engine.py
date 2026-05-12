"""Sync engine - orchestrates data sync from source to destination."""

from typing import Optional, List, Dict, Any, Iterator
from datetime import datetime
import time

from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..models.sync import SyncJob, SyncRun, SyncMode, SyncStatus
from ..models.segment import Segment, SegmentSourceType
from ..adapters.sources import SourceAdapterFactory, SourceConfig
from ..adapters.destinations import DestinationAdapterFactory, DestinationConfig, FieldMapping as AdapterFieldMapping
from ..core.security import decrypt_credential
from ..core.config import get_settings
from ..core.logging import get_logger
from . import cube_client
from .sync_service import SyncService
from .customer_service import CustomerService

logger = get_logger(__name__)
settings = get_settings()


class SyncEngine:
    """
    Sync engine that orchestrates data transfer from source to destination.
    
    Supports:
    - Full refresh sync
    - Incremental sync with checkpoint
    - Batch processing
    - Error handling with retries
    - Schema change detection
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.sync_service = SyncService(db)
    
    def execute_sync(
        self, 
        job_id: int, 
        force_full_refresh: bool = False,
        airflow_run_id: Optional[str] = None,
    ) -> SyncRun:
        """
        Execute a sync job.
        
        Args:
            job_id: ID of the sync job to execute
            force_full_refresh: If True, ignore incremental settings
            airflow_run_id: Optional Airflow run ID for tracking
        
        Returns:
            SyncRun with results
        """
        # Get sync job
        job = self.sync_service.get_sync_job(job_id)
        if not job:
            raise ValueError(f"Sync job {job_id} not found")
        
        if not job.is_active or job.is_paused:
            raise ValueError(f"Sync job {job_id} is not active or is paused")
        
        # Create sync run
        run = self.sync_service.create_sync_run(job_id, airflow_run_id)
        
        try:
            # Start run
            run = self.sync_service.start_run(run.run_id)
            
            # Execute sync
            result = self._do_sync(job, run, force_full_refresh)

            # Mark run failed when everything read was rejected by destination.
            if result["rows_failed"] > 0 and result["rows_synced"] == 0:
                run = self.sync_service.fail_run(
                    run_id=run.run_id,
                    error_message=result.get("error_message") or "All records in sync run failed",
                    error_details={"failure_type": "all_rows_failed"},
                    rows_read=result["rows_read"],
                    rows_synced=result["rows_synced"],
                    rows_failed=result["rows_failed"],
                    logs=result.get("logs"),
                )
                return run
            
            # Complete run
            run = self.sync_service.complete_run(
                run_id=run.run_id,
                rows_read=result["rows_read"],
                rows_synced=result["rows_synced"],
                rows_failed=result["rows_failed"],
                rows_skipped=result["rows_skipped"],
                new_checkpoint_value=result.get("new_checkpoint_value"),
                logs=result.get("logs"),
            )
            
            return run
            
        except Exception as e:
            logger.error("Sync failed", job_id=job_id, run_id=run.run_id, error=str(e))
            
            # Fail run
            run = self.sync_service.fail_run(
                run_id=run.run_id,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
            )
            
            # Check if should retry
            if run.retry_count < settings.max_retries:
                self.sync_service.increment_retry_count(run.run_id)
            
            return run
    
    def _do_sync(
        self,
        job: SyncJob,
        run: SyncRun,
        force_full_refresh: bool,
    ) -> Dict[str, Any]:
        """Execute the actual sync logic.

        Dispatches on the job's source shape:
          - source_segment_id set  -> resolve segment, stream rows from
            Cube (or legacy DB) into the destination.
          - else                   -> table-based path through SourceAdapter.
        """
        logs = []
        logs.append(f"[{datetime.utcnow().isoformat()}] Starting sync: {job.name}")

        # Determine sync mode
        is_incremental = (
            job.sync_mode == SyncMode.INCREMENTAL
            and job.incremental_column
            and job.last_checkpoint_value
            and not force_full_refresh
        )

        logs.append(f"[{datetime.utcnow().isoformat()}] Sync mode: {'incremental' if is_incremental else 'full_refresh'}")

        if job.source_segment_id is not None:
            return self._do_segment_sync(job, run, logs)

        # ----- Table-based (existing) path -----
        # Create source adapter
        source_conn = job.source_connection
        source_config = SourceConfig(
            host=source_conn.host,
            port=source_conn.port,
            database=source_conn.database,
            username=source_conn.username,
            password=decrypt_credential(source_conn.password_encrypted) if source_conn.password_encrypted else None,
            duckdb_path=source_conn.duckdb_path,
            extra_config=source_conn.extra_config,
        )
        source_adapter = SourceAdapterFactory.create(source_conn.source_type.value, source_config)

        # Create destination adapter
        dest_conn = job.destination_connection
        dest_config = DestinationConfig(
            api_key=decrypt_credential(dest_conn.api_key_encrypted),
            api_endpoint=dest_conn.api_endpoint or dest_conn.attentive_api_url,
            batch_size=dest_conn.batch_size or 75,
            rate_limit_per_second=dest_conn.rate_limit_per_second or 100,
            extra_config=dest_conn.extra_config,
        )
        dest_adapter = DestinationAdapterFactory.create(dest_conn.destination_type.value, dest_config)

        # Build field mappings for destination adapter
        field_mappings = [
            AdapterFieldMapping(
                source_field=m.source_field,
                destination_field=m.destination_field,
                transformation=m.transformation,
                is_sync_key=m.is_sync_key,
            )
            for m in job.field_mappings
        ]

        # Build source columns list
        source_columns = [m.source_field for m in job.field_mappings]
        if job.incremental_column and job.incremental_column not in source_columns:
            source_columns.append(job.incremental_column)

        # Build query
        if job.source_query:
            query = job.source_query
            if is_incremental:
                # Append WHERE clause to custom query
                query = f"""
                    SELECT * FROM ({job.source_query}) subq
                    WHERE "{job.incremental_column}" > '{job.last_checkpoint_value}'
                    ORDER BY "{job.incremental_column}" ASC
                """
        else:
            query = source_adapter.build_select_query(
                schema=job.source_schema,
                table=job.source_table,
                columns=source_columns,
                incremental_column=job.incremental_column if is_incremental else None,
                checkpoint_value=job.last_checkpoint_value if is_incremental else None,
            )

        logs.append(f"[{datetime.utcnow().isoformat()}] Executing query: {query[:200]}...")

        # Execute sync with batching
        rows_read = 0
        rows_synced = 0
        rows_failed = 0
        rows_skipped = 0
        new_checkpoint_value = None
        first_error_message = None
        batch_size = dest_conn.batch_size or settings.sync_batch_size
        synced_records = []  # Collect for Customer 360 profile building

        with source_adapter:
            # Check for schema changes
            current_hash = source_adapter.get_schema_hash(job.source_schema, job.source_table)
            if job.source_schema_hash and current_hash != job.source_schema_hash:
                logs.append(f"[{datetime.utcnow().isoformat()}] WARNING: Schema change detected!")

            # Stream data in batches
            for batch in source_adapter.stream_query(query, batch_size):
                batch_size_actual = len(batch)
                rows_read += batch_size_actual
                
                # Track checkpoint value
                if job.incremental_column:
                    for record in batch:
                        val = record.get(job.incremental_column)
                        if val:
                            val_str = str(val)
                            if new_checkpoint_value is None or val_str > new_checkpoint_value:
                                new_checkpoint_value = val_str
                
                # Skip empty batches
                if not batch:
                    continue
                
                # Send to destination with retry
                try:
                    result = self._send_batch_with_retry(
                        dest_adapter, 
                        batch, 
                        field_mappings, 
                        job.sync_key,
                    )
                    
                    rows_synced += result.records_sent
                    rows_failed += result.records_failed
                    rows_skipped += result.records_skipped
                    
                    # Collect synced records for profile building
                    if result.records_sent > 0:
                        synced_records.extend(batch[:result.records_sent])
                    
                    if result.errors:
                        for err in result.errors[:5]:  # Log first 5 errors
                            logs.append(f"[{datetime.utcnow().isoformat()}] Error: {err}")
                        if first_error_message is None:
                            first_error_message = str(result.errors[0])
                    
                except Exception as e:
                    rows_failed += batch_size_actual
                    logs.append(f"[{datetime.utcnow().isoformat()}] Batch failed: {str(e)}")
                    if first_error_message is None:
                        first_error_message = str(e)
                
                # Rate limiting
                time.sleep(1 / dest_config.rate_limit_per_second)
        
        # Update schema hash
        job.source_schema_hash = current_hash
        job.last_schema_check_at = datetime.utcnow()
        self.db.commit()
        
        logs.append(f"[{datetime.utcnow().isoformat()}] Sync completed: {rows_synced} synced, {rows_failed} failed")
        
        # Build Customer 360 profiles from synced records
        if synced_records and rows_synced > 0:
            try:
                customer_service = CustomerService(self.db)
                profile_result = customer_service.build_profiles_from_sync(
                    records=synced_records,
                    source_connection_id=source_conn.id,
                    sync_run_id=run.run_id,
                    sync_key=job.sync_key or "external_id",
                )
                logs.append(
                    f"[{datetime.utcnow().isoformat()}] Customer profiles: "
                    f"{profile_result.profiles_created} created, "
                    f"{profile_result.profiles_updated} updated"
                )
            except Exception as e:
                logger.warning("Profile building failed", error=str(e))
                logs.append(f"[{datetime.utcnow().isoformat()}] Profile building warning: {str(e)}")
        
        return {
            "rows_read": rows_read,
            "rows_synced": rows_synced,
            "rows_failed": rows_failed,
            "rows_skipped": rows_skipped,
            "new_checkpoint_value": new_checkpoint_value,
            "error_message": first_error_message,
            "logs": "\n".join(logs),
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    def _send_batch_with_retry(
        self,
        dest_adapter,
        batch: List[Dict[str, Any]],
        field_mappings: List[AdapterFieldMapping],
        sync_key: str,
    ):
        """Send batch to destination with retry logic."""
        return dest_adapter.sync_records(batch, field_mappings, sync_key)
    
    def check_schema_changes(self, job_id: int) -> Dict[str, Any]:
        """Check for schema changes in source table."""
        job = self.sync_service.get_sync_job(job_id)
        if not job:
            raise ValueError(f"Sync job {job_id} not found")
        
        # Create source adapter
        source_conn = job.source_connection
        source_config = SourceConfig(
            host=source_conn.host,
            port=source_conn.port,
            database=source_conn.database,
            username=source_conn.username,
            password=decrypt_credential(source_conn.password_encrypted) if source_conn.password_encrypted else None,
            duckdb_path=source_conn.duckdb_path,
        )
        source_adapter = SourceAdapterFactory.create(source_conn.source_type.value, source_config)
        
        with source_adapter:
            has_changes, current_hash, added, removed, modified = source_adapter.detect_schema_changes(
                job.source_schema,
                job.source_table,
                job.source_schema_hash,
            )
            
            # Update job
            job.source_schema_hash = current_hash
            job.last_schema_check_at = datetime.utcnow()
            self.db.commit()

            return {
                "has_changes": has_changes,
                "current_hash": current_hash,
                "previous_hash": job.source_schema_hash,
                "added_columns": added,
                "removed_columns": removed,
                "modified_columns": modified,
            }

    # =========================================================================
    # Segment-driven sync path
    # =========================================================================

    def _do_segment_sync(
        self,
        job: SyncJob,
        run: SyncRun,
        logs: List[str],
    ) -> Dict[str, Any]:
        """Resolve the job's segment, stream audience rows, feed destination.

        Mirrors the table-source loop: read batches, apply field mappings,
        send to destination adapter, accumulate metrics. Skips the
        SourceAdapter (no DB connection to manage) and schema-hash logic
        (segments are governed by Cube, not raw table shapes).
        """
        segment: Optional[Segment] = (
            self.db.query(Segment).filter(Segment.id == job.source_segment_id).first()
        )
        if not segment:
            raise ValueError(f"Segment {job.source_segment_id} (referenced by sync {job.id}) not found")

        logs.append(
            f"[{datetime.utcnow().isoformat()}] Source: segment {segment.id} "
            f"'{segment.name}' ({segment.source_type})"
        )

        # Destination adapter (same path as table-sync).
        dest_conn = job.destination_connection
        dest_config = DestinationConfig(
            api_key=decrypt_credential(dest_conn.api_key_encrypted),
            api_endpoint=dest_conn.api_endpoint or dest_conn.attentive_api_url,
            batch_size=dest_conn.batch_size or 75,
            rate_limit_per_second=dest_conn.rate_limit_per_second or 100,
            extra_config=dest_conn.extra_config,
        )
        dest_adapter = DestinationAdapterFactory.create(dest_conn.destination_type.value, dest_config)

        field_mappings = [
            AdapterFieldMapping(
                source_field=m.source_field,
                destination_field=m.destination_field,
                transformation=m.transformation,
                is_sync_key=m.is_sync_key,
            )
            for m in job.field_mappings
        ]

        batch_size = dest_conn.batch_size or settings.sync_batch_size
        rows_read = 0
        rows_synced = 0
        rows_failed = 0
        rows_skipped = 0
        first_error_message: Optional[str] = None
        synced_records: List[Dict[str, Any]] = []

        for batch in self._iter_segment_rows(segment, batch_size, logs):
            rows_read += len(batch)
            if not batch:
                continue
            try:
                result = self._send_batch_with_retry(dest_adapter, batch, field_mappings, job.sync_key)
                rows_synced += result.records_sent
                rows_failed += result.records_failed
                rows_skipped += result.records_skipped
                if result.records_sent > 0:
                    synced_records.extend(batch[:result.records_sent])
                if result.errors:
                    for err in result.errors[:5]:
                        logs.append(f"[{datetime.utcnow().isoformat()}] Error: {err}")
                    if first_error_message is None:
                        first_error_message = str(result.errors[0])
            except Exception as e:
                rows_failed += len(batch)
                logs.append(f"[{datetime.utcnow().isoformat()}] Batch failed: {e}")
                if first_error_message is None:
                    first_error_message = str(e)
            # Respect destination rate limit
            time.sleep(1 / dest_config.rate_limit_per_second)

        logs.append(
            f"[{datetime.utcnow().isoformat()}] Segment sync completed: "
            f"{rows_synced} synced, {rows_failed} failed, {rows_skipped} skipped"
        )

        # Update segment's cached count so the UI reflects fresh activity.
        try:
            segment.estimated_count = rows_read
            segment.last_count_at = datetime.utcnow()
            self.db.commit()
        except Exception as e:
            logger.warning("Failed to update segment count after sync", error=str(e))

        return {
            "rows_read": rows_read,
            "rows_synced": rows_synced,
            "rows_failed": rows_failed,
            "rows_skipped": rows_skipped,
            "new_checkpoint_value": None,
            "error_message": first_error_message,
            "logs": "\n".join(logs),
        }

    def _iter_segment_rows(
        self,
        segment: Segment,
        batch_size: int,
        logs: List[str],
    ) -> Iterator[List[Dict[str, Any]]]:
        """Yield batches of rows from a segment.

        - cube:   strip the Cube prefix from each column so field mappings
                  written against `email` / `customer_id` work without
                  needing to know about `customer_unified.email`.
                  Honors the cube_query's `limit` as the audience cap.
        - legacy: pages through CustomerProfile (limit/offset).
        """
        if segment.source_type == SegmentSourceType.CUBE.value:
            cube_query = segment.cube_query or {}
            try:
                result = cube_client.cube_load(cube_query)
            except (cube_client.CubeQueryError, cube_client.CubeUnavailableError) as e:
                raise RuntimeError(f"Cube segment fetch failed: {e}")
            rows = result.get("data", []) or []
            logs.append(f"[{datetime.utcnow().isoformat()}] Cube returned {len(rows)} rows for audience")
            stripped = [_strip_cube_prefix(r) for r in rows]
            for i in range(0, len(stripped), batch_size):
                yield stripped[i:i + batch_size]
            return

        # Legacy CustomerProfile segment: page through the filtered query.
        from .segment_service import SegmentService  # local import to avoid cycle
        svc = SegmentService(self.db)
        # Determine total via existing preview (no sample needed).
        page = 1
        page_size = max(batch_size, 100)
        while True:
            customers, total = svc.get_segment_customers(segment.id, page=page, page_size=page_size)
            if not customers:
                break
            batch = [svc._customer_to_dict(c) for c in customers]
            yield batch
            if page * page_size >= total:
                break
            page += 1


def _strip_cube_prefix(row: Dict[str, Any]) -> Dict[str, Any]:
    """Turn `{'cube.email': 'a@b'}` into `{'email': 'a@b'}`.

    Cube returns fully-qualified keys; downstream field mappings reference
    short field names (e.g. `email`, `customer_id`). Last segment of the
    dotted name wins on collisions; keys without a dot are passed through.
    """
    out: Dict[str, Any] = {}
    for k, v in row.items():
        short = k.split(".", 1)[1] if "." in k else k
        out[short] = v
    return out
