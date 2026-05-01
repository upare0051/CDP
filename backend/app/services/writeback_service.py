"""Service for controlled write-back preview/apply from AI insights."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import duckdb
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.logging import get_logger
from ..models.customer import CustomerAttribute
from ..models.writeback import WritebackJob, WritebackRun
from ..schemas.writeback import WritebackJobCreate, WritebackJobUpdate

logger = get_logger(__name__)
settings = get_settings()


class WritebackService:
    """Controlled write-back with preview/apply and audit runs."""

    ALLOWED_SOURCE_TYPES = {"ai_customer_insights"}
    ALLOWED_TARGET_TYPES = {"customer_attributes"}
    ALLOWED_FIELD_MAPPINGS = {
        "summary",
        "churn_level",
        "churn_score",
        "engagement_score",
        "customer_segment",
    }

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------------
    # CRUD
    # ---------------------------------------------------------------------
    def create_job(self, data: WritebackJobCreate) -> WritebackJob:
        self._validate_job_payload(
            source_type=data.source_type,
            target_type=data.target_type,
            value_mapping=data.value_mapping.model_dump(),
        )
        job = WritebackJob(
            name=data.name,
            description=data.description,
            source_type=data.source_type,
            source_filters=data.source_filters,
            target_type=data.target_type,
            attribute_name=data.attribute_name,
            attribute_type=data.attribute_type,
            value_mapping=data.value_mapping.model_dump(),
            status="draft",
            created_by=data.created_by,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(self) -> List[WritebackJob]:
        return self.db.query(WritebackJob).order_by(WritebackJob.updated_at.desc()).all()

    def get_job(self, job_id: int) -> Optional[WritebackJob]:
        return self.db.query(WritebackJob).filter(WritebackJob.id == job_id).first()

    def update_job(self, job_id: int, data: WritebackJobUpdate) -> Optional[WritebackJob]:
        job = self.get_job(job_id)
        if not job:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "value_mapping" in update_data and update_data["value_mapping"] is not None:
            update_data["value_mapping"] = update_data["value_mapping"]

        for key, value in update_data.items():
            setattr(job, key, value)

        self._validate_job_payload(
            source_type=job.source_type,
            target_type=job.target_type,
            value_mapping=job.value_mapping,
        )
        self.db.commit()
        self.db.refresh(job)
        return job

    # ---------------------------------------------------------------------
    # Preview / Apply
    # ---------------------------------------------------------------------
    def preview_job(self, job_id: int, limit: int = 20) -> Tuple[WritebackRun, List[Dict[str, Any]]]:
        job = self.get_job(job_id)
        if not job:
            raise ValueError("Writeback job not found")

        candidates = self._fetch_candidates(job, limit=10000)
        sample = candidates[:limit]

        run = WritebackRun(
            job_id=job.id,
            run_type="preview",
            status="completed",
            total_candidates=len(candidates),
            sample_preview=sample,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run, sample

    def apply_job(self, job_id: int) -> WritebackRun:
        job = self.get_job(job_id)
        if not job:
            raise ValueError("Writeback job not found")

        run = WritebackRun(
            job_id=job.id,
            run_type="apply",
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            candidates = self._fetch_candidates(job, limit=200000)
            run.total_candidates = len(candidates)

            updates = 0
            inserts = 0
            failures = 0

            for row in candidates:
                try:
                    customer_id = int(row["customer_id"])
                    mapped_value = self._map_value(job.value_mapping, row)
                    mapped_value_str = None if mapped_value is None else str(mapped_value)

                    existing_attr = (
                        self.db.query(CustomerAttribute)
                        .filter(
                            CustomerAttribute.customer_id == customer_id,
                            CustomerAttribute.attribute_name == job.attribute_name,
                        )
                        .first()
                    )
                    if existing_attr:
                        existing_attr.attribute_value = mapped_value_str
                        existing_attr.attribute_type = job.attribute_type
                        existing_attr.updated_at = datetime.utcnow()
                        updates += 1
                    else:
                        new_attr = CustomerAttribute(
                            customer_id=customer_id,
                            attribute_name=job.attribute_name,
                            attribute_value=mapped_value_str,
                            attribute_type=job.attribute_type,
                            source_field=f"writeback:{job.id}",
                        )
                        self.db.add(new_attr)
                        inserts += 1
                except Exception:
                    failures += 1

            run.status = "completed"
            run.total_updates = updates
            run.total_inserts = inserts
            run.total_failed = failures
            run.completed_at = datetime.utcnow()
            run.sample_preview = candidates[:20]
            job.status = "active"

            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
            return run

    def list_runs(self, job_id: int, limit: int = 20) -> List[WritebackRun]:
        return (
            self.db.query(WritebackRun)
            .filter(WritebackRun.job_id == job_id)
            .order_by(WritebackRun.created_at.desc())
            .limit(limit)
            .all()
        )

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _validate_job_payload(
        self,
        source_type: str,
        target_type: str,
        value_mapping: Dict[str, Any],
    ) -> None:
        if source_type not in self.ALLOWED_SOURCE_TYPES:
            raise ValueError(f"Unsupported source_type: {source_type}")
        if target_type not in self.ALLOWED_TARGET_TYPES:
            raise ValueError(f"Unsupported target_type: {target_type}")

        mode = value_mapping.get("mode")
        if mode == "field":
            field = value_mapping.get("field")
            if field not in self.ALLOWED_FIELD_MAPPINGS:
                raise ValueError(f"Field mapping '{field}' is not whitelisted")
        elif mode == "static":
            if value_mapping.get("value") is None:
                raise ValueError("Static value mapping requires 'value'")
        else:
            raise ValueError(f"Unsupported value mapping mode: {mode}")

    def _duckdb_connect(self):
        return duckdb.connect(settings.dbt_duckdb_path, read_only=True)

    def _fetch_candidates(self, job: WritebackJob, limit: int) -> List[Dict[str, Any]]:
        if job.source_type != "ai_customer_insights":
            raise ValueError("Only ai_customer_insights source is currently supported")

        filters = job.source_filters or {}
        where_clauses = ["insight_kind = 'profile_analysis'"]
        params: List[Any] = []

        # Supported filters for controlled and predictable preview/apply behavior.
        if filters.get("churn_level"):
            where_clauses.append("churn_level = ?")
            params.append(filters["churn_level"])
        if filters.get("customer_segment"):
            where_clauses.append("customer_segment = ?")
            params.append(filters["customer_segment"])
        if filters.get("min_churn_score") is not None:
            where_clauses.append("churn_score >= ?")
            params.append(float(filters["min_churn_score"]))
        if filters.get("max_churn_score") is not None:
            where_clauses.append("churn_score <= ?")
            params.append(float(filters["max_churn_score"]))
        if filters.get("min_engagement_score") is not None:
            where_clauses.append("engagement_score >= ?")
            params.append(float(filters["min_engagement_score"]))
        if filters.get("max_engagement_score") is not None:
            where_clauses.append("engagement_score <= ?")
            params.append(float(filters["max_engagement_score"]))

        query = f"""
            WITH latest_per_customer AS (
                SELECT
                    customer_id,
                    max(created_at) AS max_created_at
                FROM ai_customer_insights
                WHERE {" AND ".join(where_clauses)}
                GROUP BY customer_id
            )
            SELECT i.customer_id, i.external_id, i.summary, i.churn_score, i.churn_level,
                   i.engagement_score, i.customer_segment
            FROM ai_customer_insights i
            JOIN latest_per_customer l
              ON i.customer_id = l.customer_id
             AND i.created_at = l.max_created_at
            ORDER BY i.customer_id ASC
            LIMIT {int(limit)}
        """

        with self._duckdb_connect() as conn:
            rows = conn.execute(query, params).fetchall()
            cols = [c[0] for c in conn.description]

        return [dict(zip(cols, row)) for row in rows]

    def _map_value(self, value_mapping: Dict[str, Any], row: Dict[str, Any]) -> Any:
        mode = value_mapping.get("mode")
        if mode == "static":
            return value_mapping.get("value")
        if mode == "field":
            field = value_mapping.get("field")
            return row.get(field)
        return None
