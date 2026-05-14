"""Materialize app segments into Redshift publication tables."""

from __future__ import annotations

import json
import re
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.logging import get_logger
from ..models.segment import Segment, SegmentSourceType
from ..models.segment_refresh import SegmentRefreshRun
from ..schemas.segment import FilterConfig
from . import cube_client, dittofeed_client
from .segment_service import SegmentService

logger = get_logger(__name__)
settings = get_settings()

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Invalid Redshift identifier: {name!r}")
    return name


def _strip_cube_prefix(row: Dict[str, Any]) -> Dict[str, Any]:
    """Turn `customer_unified.customer_id` into `customer_id` for payloads."""
    out: Dict[str, Any] = {}
    for key, value in row.items():
        short = key.split(".", 1)[1] if "." in key else key
        out[short] = value
    return out


class SegmentMaterializationService:
    """Resolve segment members and write the fixed Redshift segment schema."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def sync_segment_to_redshift(self, segment_id: int, trigger: str = "manual") -> SegmentRefreshRun:
        """Synchronously materialize one segment to Redshift and record a run."""
        segment = self.db.query(Segment).filter(Segment.id == segment_id).first()
        if not segment:
            raise ValueError(f"Segment {segment_id} not found")

        run = SegmentRefreshRun(
            segment_id=segment_id,
            run_id=str(uuid.uuid4()),
            target="redshift",
            status="running",
            trigger=trigger,
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            self.ensure_redshift_storage()
            rows = self._resolve_segment_rows(segment)
            row_count = self._write_redshift(segment, run.run_id, rows)

            segment.estimated_count = row_count
            segment.last_count_at = datetime.utcnow()
            run.status = "succeeded"
            run.row_count = row_count
            run.finished_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
            logger.info("Segment materialized to Redshift", segment_id=segment.id, run_id=run.run_id, rows=row_count)
            self._mirror_membership_to_dittofeed(segment, rows)
            return run
        except Exception as e:
            self.db.rollback()
            run = self.db.query(SegmentRefreshRun).filter(SegmentRefreshRun.id == run.id).first()
            if run:
                run.status = "failed"
                run.error_message = str(e)
                run.finished_at = datetime.utcnow()
                self.db.commit()
                self.db.refresh(run)
                logger.error("Segment Redshift materialization failed", segment_id=segment.id, run_id=run.run_id, error=str(e))
                return run
            raise

    def list_runs(self, segment_id: int, limit: int = 10) -> List[SegmentRefreshRun]:
        """Return recent Redshift materialization runs for a segment."""
        return (
            self.db.query(SegmentRefreshRun)
            .filter(SegmentRefreshRun.segment_id == segment_id)
            .order_by(SegmentRefreshRun.started_at.desc())
            .limit(limit)
            .all()
        )

    def get_run(self, segment_id: int, run_id: str) -> Optional[SegmentRefreshRun]:
        """Return one materialization run."""
        return (
            self.db.query(SegmentRefreshRun)
            .filter(
                SegmentRefreshRun.segment_id == segment_id,
                SegmentRefreshRun.run_id == run_id,
            )
            .first()
        )

    def ensure_redshift_storage(self) -> None:
        """Create Redshift segment storage tables if they do not already exist."""
        schema = _validate_ident(settings.segment_redshift_schema)
        try:
            with self._connect_redshift() as conn:
                cur = conn.cursor()
                self._ensure_redshift_tables(cur, schema)
                conn.commit()
        except Exception as e:
            raise RuntimeError(f"Redshift storage setup failed: {e}") from e

    # ------------------------------------------------------------------
    # Segment resolution
    # ------------------------------------------------------------------
    def _resolve_segment_rows(self, segment: Segment) -> List[Dict[str, Any]]:
        if segment.source_type == SegmentSourceType.CUBE.value:
            query = self._cube_materialization_query(segment.cube_query or {})
            try:
                result = cube_client.cube_load(
                    query,
                    max_wait_seconds=settings.segment_cube_timeout_seconds,
                    request_timeout_seconds=settings.segment_cube_timeout_seconds,
                )
                return [_strip_cube_prefix(row) for row in (result.get("data", []) or [])]
            except Exception as e:
                raise RuntimeError(f"Cube audience extraction failed before Redshift write: {e}") from e

        svc = SegmentService(self.db)
        filter_config = FilterConfig(**(segment.filter_config or {"filters": [], "logic": "AND"}))
        query = svc._build_segment_query(filter_config)
        return [svc._customer_to_dict(customer) for customer in query.all()]

    def _cube_materialization_query(self, cube_query: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure Cube row extraction includes Braze-compatible identity fields."""
        if not cube_query:
            raise ValueError("Cube segment has no query definition")

        query = SegmentService.normalize_cube_query(cube_query)
        dimensions = list(query.get("dimensions") or [])

        source = None
        if dimensions and "." in dimensions[0]:
            source = dimensions[0].split(".", 1)[0]
        else:
            member = SegmentService.first_cube_member(query)
            if member and "." in member:
                source = member.split(".", 1)[0]
        source = source or "customer_unified"

        identity_fields = ("customer_id",)
        if source in {"customer_360", "customer_marketing", "customer_unified", "customer_unified_attr", "customer_identifier_dim"}:
            identity_fields = ("phone", "email", "customer_id")

        for identity_field in identity_fields:
            member = f"{source}.{identity_field}"
            if not any(d == member or d.split(".")[-1] == identity_field for d in dimensions):
                dimensions.insert(0, member)

        query["dimensions"] = dimensions
        return query

    # ------------------------------------------------------------------
    # Redshift writer
    # ------------------------------------------------------------------
    def _write_redshift(self, segment: Segment, run_id: str, rows: List[Dict[str, Any]]) -> int:
        schema = _validate_ident(settings.segment_redshift_schema)
        refreshed_at = datetime.now(timezone.utc)

        with self._connect_redshift() as conn:
            cur = conn.cursor()
            try:
                self._ensure_redshift_tables(cur, schema)
                segment_data_columns = self._table_columns(cur, schema, "segment_data")
                segment_data_types = self._table_column_types(cur, schema, "segment_data")
                self._validate_braze_segment_data_types(schema, segment_data_types)

                cur.execute(
                    f"DELETE FROM {schema}.segment_metadata WHERE segment_id = %s",
                    (int(segment.id),),
                )
                cur.execute(
                    f"""
                    INSERT INTO {schema}.segment_metadata
                        (segment_id, segment_title, segment_desc, created, updated, last_refreshed_dt)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        int(segment.id),
                        segment.name,
                        segment.description,
                        segment.created_at,
                        segment.updated_at,
                        refreshed_at,
                    ),
                )

                insert_columns, insert_sql = self._segment_data_insert_sql(
                    schema,
                    segment_data_columns,
                    segment_data_types,
                )
                batch: List[tuple[Any, ...]] = []
                row_count = 0
                for row in rows:
                    cust_id = self._extract_customer_id(row)
                    external_id = self._extract_external_id(row, cust_id)
                    email = self._extract_optional_str(row, ("email", "email_norm"))
                    phone = self._extract_optional_str(row, ("phone", "phone_norm"))
                    payload = json.dumps(row, default=str)
                    value_by_column: Dict[str, Any] = {
                        "seg_id": int(segment.id),
                        "cust_id": cust_id,
                        "external_id": external_id,
                        "email": email,
                        "phone": phone,
                        "payload": payload,
                        "json_payload": payload,
                        "run_id": run_id,
                        "updated_at": refreshed_at,
                        "refreshed_at": refreshed_at,
                    }
                    batch.append(tuple(value_by_column[column] for column in insert_columns))
                    if len(batch) >= settings.segment_redshift_batch_size:
                        cur.executemany(insert_sql, batch)
                        row_count += len(batch)
                        batch = []
                if batch:
                    cur.executemany(insert_sql, batch)
                    row_count += len(batch)

                cur.execute(f"DELETE FROM {schema}.segment_latest_run WHERE seg_id = %s", (int(segment.id),))
                cur.execute(
                    f"""
                    INSERT INTO {schema}.segment_latest_run (seg_id, run_id, refreshed_at, row_count)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (int(segment.id), run_id, refreshed_at, row_count),
                )

                conn.commit()
                return row_count
            except Exception:
                conn.rollback()
                raise

    def _connect_redshift(self):
        host = settings.segment_redshift_host or settings.redshift_host
        port = settings.segment_redshift_port or settings.redshift_port
        database = settings.segment_redshift_database or settings.redshift_database
        user = settings.segment_redshift_user or settings.redshift_user
        password = settings.segment_redshift_password or settings.redshift_password
        if not host or not user or not database:
            raise ValueError(
                "Redshift materialization is not configured. Set REDSHIFT_HOST, "
                "REDSHIFT_USER, REDSHIFT_DATABASE, and password if required."
            )

        import redshift_connector  # noqa: WPS433

        conn = redshift_connector.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            ssl=settings.c360_redshift_ssl,
            timeout=settings.segment_redshift_timeout_seconds,
        )
        return closing(conn)

    def _ensure_redshift_tables(self, cur, schema: str) -> None:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.segment_metadata (
                segment_id          BIGINT       NOT NULL,
                segment_title       VARCHAR(512) NOT NULL,
                segment_desc        VARCHAR(8192),
                created             TIMESTAMP    NOT NULL DEFAULT GETDATE(),
                updated             TIMESTAMP    NOT NULL DEFAULT GETDATE(),
                last_refreshed_dt   TIMESTAMP,
                PRIMARY KEY (segment_id)
            )
            DISTSTYLE KEY
            DISTKEY (segment_id)
            SORTKEY (segment_id)
            """
        )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.segment_data (
                seg_id          BIGINT        NOT NULL,
                external_id     VARCHAR(256)  NOT NULL,
                email           VARCHAR(512),
                phone           VARCHAR(64),
                payload         VARCHAR(65535),
                updated_at      TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                run_id          VARCHAR(64)   NOT NULL,
                cust_id         BIGINT,
                PRIMARY KEY (seg_id, external_id, run_id)
            )
            DISTSTYLE KEY
            DISTKEY (external_id)
            COMPOUND SORTKEY (seg_id, run_id, updated_at)
            """
        )
        self._ensure_column(cur, schema, "segment_data", "external_id", "VARCHAR(256)")
        self._ensure_column(cur, schema, "segment_data", "email", "VARCHAR(512)")
        self._ensure_column(cur, schema, "segment_data", "phone", "VARCHAR(64)")
        self._ensure_column(cur, schema, "segment_data", "payload", "VARCHAR(65535)")
        self._ensure_column(cur, schema, "segment_data", "updated_at", "TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.segment_latest_run (
                seg_id        BIGINT       NOT NULL,
                run_id        VARCHAR(64)  NOT NULL,
                refreshed_at  TIMESTAMP    NOT NULL,
                row_count     BIGINT,
                PRIMARY KEY (seg_id)
            )
            DISTSTYLE ALL
            """
        )

    def _ensure_column(self, cur, schema: str, table: str, column: str, ddl: str) -> None:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND column_name = %s
            """,
            (schema, table, column),
        )
        if not cur.fetchone():
            cur.execute(f"ALTER TABLE {schema}.{table} ADD COLUMN {column} {ddl}")

    def _table_column_types(self, cur, schema: str, table: str) -> Dict[str, str]:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (schema, table),
        )
        return {str(row[0]).lower(): str(row[1]).lower() for row in cur.fetchall()}

    def _validate_braze_segment_data_types(self, schema: str, column_types: Dict[str, str]) -> None:
        payload_type = column_types.get("payload", "")
        updated_at_type = column_types.get("updated_at", "")
        if "char" not in payload_type and "text" not in payload_type:
            raise RuntimeError(
                f"{schema}.segment_data.payload must be VARCHAR for Braze, found {payload_type or 'missing'}. "
                f"Recreate {schema}.segment_data with the latest ext_braze DDL, then rerun the sync."
            )
        if "with time zone" not in updated_at_type and "timestamptz" not in updated_at_type:
            raise RuntimeError(
                f"{schema}.segment_data.updated_at must be TIMESTAMPTZ for Braze, found {updated_at_type or 'missing'}. "
                f"Recreate {schema}.segment_data with the latest ext_braze DDL, then rerun the sync."
            )

    def _table_columns(self, cur, schema: str, table: str) -> set[str]:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (schema, table),
        )
        return {str(row[0]).lower() for row in cur.fetchall()}

    def _segment_data_insert_sql(
        self,
        schema: str,
        columns: set[str],
        column_types: Dict[str, str],
    ) -> tuple[List[str], str]:
        preferred_columns = [
            "seg_id",
            "external_id",
            "email",
            "phone",
            "payload",
            "updated_at",
            "run_id",
            "cust_id",
            "json_payload",
            "refreshed_at",
        ]
        insert_columns = [column for column in preferred_columns if column in columns]
        value_exprs = []
        for column in insert_columns:
            is_json_column = column in {"payload", "json_payload"}
            is_super = "super" in column_types.get(column, "")
            value_exprs.append("JSON_PARSE(%s)" if is_json_column and is_super else "%s")

        return insert_columns, f"""
            INSERT INTO {schema}.segment_data
                ({", ".join(insert_columns)})
            VALUES ({", ".join(value_exprs)})
        """

    # ------------------------------------------------------------------
    # Dittofeed mirror — push current members so the mirrored Manual segment
    # actually advances users in the journey engine. Best-effort: a failure
    # here must not roll back the Redshift run.
    # ------------------------------------------------------------------
    def _mirror_membership_to_dittofeed(
        self, segment: Segment, rows: List[Dict[str, Any]]
    ) -> None:
        df_id = segment.dittofeed_segment_id
        if not df_id:
            return
        user_ids: List[str] = []
        for row in rows:
            ext = row.get("external_id")
            if ext is not None and ext != "":
                user_ids.append(str(ext))
        if not user_ids:
            logger.info(
                "Dittofeed mirror membership skipped: no external_id in rows",
                segment_id=segment.id,
            )
            return
        try:
            dittofeed_client.update_manual_segment_members(
                df_id, user_ids, append=True
            )
            logger.info(
                "Pushed segment membership to Dittofeed",
                segment_id=segment.id,
                dittofeed_segment_id=df_id,
                count=len(user_ids),
            )
        except dittofeed_client.DittofeedError as e:
            logger.warning(
                "Dittofeed membership push failed",
                segment_id=segment.id,
                error=str(e),
            )

    def _extract_external_id(self, row: Dict[str, Any], fallback_customer_id: int) -> str:
        value = self._extract_optional_str(row, ("external_id", "customer_id", "cust_id", "id"))
        return value or str(fallback_customer_id)

    def _extract_optional_str(self, row: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
        for key in keys:
            value = row.get(key)
            if value is not None and value != "":
                return str(value)
        return None

    def _extract_customer_id(self, row: Dict[str, Any]) -> int:
        for key in ("cust_id", "customer_id", "id"):
            value = row.get(key)
            if value is not None and value != "":
                try:
                    return int(value)
                except (TypeError, ValueError):
                    raise ValueError(f"Segment row has non-numeric {key}: {value!r}")
        raise ValueError("Segment row does not include cust_id, customer_id, or id")
