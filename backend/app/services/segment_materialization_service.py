"""Materialize app segments into Redshift gold tables."""

from __future__ import annotations

import json
import re
import uuid
from contextlib import closing
from datetime import datetime
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
        """Ensure Cube row extraction includes a customer key for Redshift cust_id."""
        if not cube_query:
            raise ValueError("Cube segment has no query definition")

        query = dict(cube_query)
        dimensions = list(query.get("dimensions") or [])
        filters = list(query.get("filters") or [])

        has_customer_key = any(d.split(".")[-1] in {"customer_id", "cust_id", "id"} for d in dimensions)
        if not has_customer_key:
            source = None
            if dimensions and "." in dimensions[0]:
                source = dimensions[0].split(".", 1)[0]
            else:
                for item in filters:
                    member = str(item.get("member") or "")
                    if "." in member:
                        source = member.split(".", 1)[0]
                        break
            source = source or "customer_unified"
            dimensions.insert(0, f"{source}.customer_id")

        query["dimensions"] = dimensions
        return query

    # ------------------------------------------------------------------
    # Redshift writer
    # ------------------------------------------------------------------
    def _write_redshift(self, segment: Segment, run_id: str, rows: List[Dict[str, Any]]) -> int:
        schema = _validate_ident(settings.segment_redshift_schema)
        refreshed_at = datetime.utcnow()

        with self._connect_redshift() as conn:
            cur = conn.cursor()
            try:
                self._ensure_redshift_tables(cur, schema)
                segment_data_columns = self._table_columns(cur, schema, "segment_data")
                json_type = self._json_payload_type(cur, schema)

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

                insert_sql = self._segment_data_insert_sql(schema, json_type, segment_data_columns)
                batch: List[tuple[Any, ...]] = []
                row_count = 0
                for row in rows:
                    cust_id = self._extract_customer_id(row)
                    payload = json.dumps(row, default=str)
                    values: List[Any] = [int(segment.id), cust_id, payload]
                    if "run_id" in segment_data_columns:
                        values.append(run_id)
                    if "refreshed_at" in segment_data_columns:
                        values.append(refreshed_at)
                    batch.append(tuple(values))
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
                seg_id          BIGINT       NOT NULL,
                cust_id         BIGINT       NOT NULL,
                json_payload    SUPER,
                run_id          VARCHAR(64)  NOT NULL,
                refreshed_at    TIMESTAMP    NOT NULL DEFAULT GETDATE(),
                PRIMARY KEY (seg_id, cust_id, run_id)
            )
            DISTSTYLE KEY
            DISTKEY (cust_id)
            COMPOUND SORTKEY (cust_id, seg_id, run_id)
            """
        )
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

    def _json_payload_type(self, cur, schema: str) -> str:
        cur.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = 'segment_data'
              AND column_name = 'json_payload'
            """,
            (schema,),
        )
        row = cur.fetchone()
        return str(row[0]).lower() if row else "super"

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

    def _segment_data_insert_sql(self, schema: str, json_type: str, columns: set[str]) -> str:
        payload_expr = "JSON_PARSE(%s)" if "super" in json_type else "%s"
        insert_columns = ["seg_id", "cust_id", "json_payload"]
        value_exprs = ["%s", "%s", payload_expr]

        if "run_id" in columns:
            insert_columns.append("run_id")
            value_exprs.append("%s")
        if "refreshed_at" in columns:
            insert_columns.append("refreshed_at")
            value_exprs.append("%s")

        return f"""
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

    def _extract_customer_id(self, row: Dict[str, Any]) -> int:
        for key in ("cust_id", "customer_id", "id"):
            value = row.get(key)
            if value is not None and value != "":
                try:
                    return int(value)
                except (TypeError, ValueError):
                    raise ValueError(f"Segment row has non-numeric {key}: {value!r}")
        raise ValueError("Segment row does not include cust_id, customer_id, or id")
