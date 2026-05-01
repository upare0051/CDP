"""Sync engine - orchestrates data sync from source to destination."""

from typing import Optional, List, Dict, Any
from datetime import datetime
import time

from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..models.sync import SyncJob, SyncRun, SyncMode, SyncStatus
from ..adapters.sources import SourceAdapterFactory, SourceConfig
from ..adapters.destinations import DestinationAdapterFactory, DestinationConfig, FieldMapping as AdapterFieldMapping
from ..core.security import decrypt_credential
from ..core.config import get_settings
from ..core.logging import get_logger
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
        """Execute the actual sync logic."""
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
