"""DuckDB persistence for AI-generated insights and recommendations."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AIInsightsStore:
    """Persists AI outputs into DuckDB for downstream analytics and teams."""

    def __init__(self, duckdb_path: Optional[str] = None):
        self.duckdb_path = duckdb_path or settings.dbt_duckdb_path
        self._ensure_parent_dir()
        self.ensure_tables()

    def _ensure_parent_dir(self) -> None:
        Path(self.duckdb_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        return duckdb.connect(self.duckdb_path)

    def ensure_tables(self) -> None:
        """Create AI persistence tables if they don't exist."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_insight_runs (
                    run_id VARCHAR PRIMARY KEY,
                    insight_kind VARCHAR,
                    source_endpoint VARCHAR,
                    model_id VARCHAR,
                    status VARCHAR,
                    is_fallback BOOLEAN,
                    latency_ms BIGINT,
                    input_ref VARCHAR,
                    meta_json JSON,
                    error_message VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_customer_insights (
                    run_id VARCHAR,
                    customer_id BIGINT,
                    external_id VARCHAR,
                    insight_kind VARCHAR,
                    summary VARCHAR,
                    churn_score DOUBLE,
                    churn_level VARCHAR,
                    engagement_score DOUBLE,
                    customer_segment VARCHAR,
                    next_best_actions_json JSON,
                    insights_json JSON,
                    payload_json JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_audience_recommendations (
                    run_id VARCHAR,
                    goal VARCHAR,
                    recommendation_index BIGINT,
                    name VARCHAR,
                    description VARCHAR,
                    rationale VARCHAR,
                    estimated_size VARCHAR,
                    potential_impact VARCHAR,
                    priority VARCHAR,
                    segment_json JSON,
                    payload_json JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def start_run(
        self,
        insight_kind: str,
        source_endpoint: str,
        model_id: str,
        input_ref: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a run record and return run_id."""
        run_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_insight_runs (
                    run_id, insight_kind, source_endpoint, model_id, status, is_fallback, input_ref, meta_json
                ) VALUES (?, ?, ?, ?, 'running', FALSE, ?, ?::JSON)
                """,
                [run_id, insight_kind, source_endpoint, model_id, input_ref, json.dumps(meta or {})],
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str = "completed",
        is_fallback: bool = False,
        latency_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Finalize run status."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ai_insight_runs
                SET status = ?,
                    is_fallback = ?,
                    latency_ms = ?,
                    error_message = ?
                WHERE run_id = ?
                """,
                [status, is_fallback, latency_ms, error_message, run_id],
            )

    def persist_customer_analysis(
        self,
        run_id: str,
        customer_id: int,
        external_id: Optional[str],
        analysis: Dict[str, Any],
    ) -> None:
        """Persist customer analysis payload and normalized fields."""
        churn = analysis.get("churn_risk", {}) if isinstance(analysis, dict) else {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_customer_insights (
                    run_id, customer_id, external_id, insight_kind, summary, churn_score, churn_level,
                    engagement_score, customer_segment, next_best_actions_json, insights_json, payload_json
                ) VALUES (?, ?, ?, 'profile_analysis', ?, ?, ?, ?, ?, ?::JSON, ?::JSON, ?::JSON)
                """,
                [
                    run_id,
                    customer_id,
                    external_id,
                    analysis.get("summary"),
                    float(churn.get("score")) if churn.get("score") is not None else None,
                    churn.get("level"),
                    float(analysis.get("engagement_score")) if analysis.get("engagement_score") is not None else None,
                    analysis.get("customer_segment"),
                    json.dumps(analysis.get("next_best_actions", [])),
                    json.dumps(analysis.get("insights", [])),
                    json.dumps(analysis),
                ],
            )

    def persist_customer_summary(
        self,
        run_id: str,
        customer_id: int,
        external_id: Optional[str],
        summary: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist summary-only AI response."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_customer_insights (
                    run_id, customer_id, external_id, insight_kind, summary, payload_json
                ) VALUES (?, ?, ?, 'summary', ?, ?::JSON)
                """,
                [run_id, customer_id, external_id, summary, json.dumps(payload or {"summary": summary})],
            )

    def persist_audience_recommendations(
        self,
        run_id: str,
        goal: str,
        recommendations: List[Dict[str, Any]],
    ) -> None:
        """Persist audience recommendations and normalized fields."""
        with self._connect() as conn:
            for idx, rec in enumerate(recommendations):
                conn.execute(
                    """
                    INSERT INTO ai_audience_recommendations (
                        run_id, goal, recommendation_index, name, description, rationale,
                        estimated_size, potential_impact, priority, segment_json, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?::JSON)
                    """,
                    [
                        run_id,
                        goal,
                        idx,
                        rec.get("name"),
                        rec.get("description"),
                        rec.get("rationale"),
                        rec.get("estimated_size"),
                        rec.get("potential_impact"),
                        rec.get("priority"),
                        json.dumps(rec.get("segment")),
                        json.dumps(rec),
                    ],
                )

    def get_status(self) -> Dict[str, Any]:
        """Return AI insights persistence status and counts."""
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            run_count = conn.execute("SELECT count(*) FROM ai_insight_runs").fetchone()[0]
            insight_count = conn.execute("SELECT count(*) FROM ai_customer_insights").fetchone()[0]
            rec_count = conn.execute("SELECT count(*) FROM ai_audience_recommendations").fetchone()[0]
            latest_run = conn.execute(
                "SELECT max(created_at) FROM ai_insight_runs"
            ).fetchone()[0]

        age_seconds = None
        if latest_run:
            # DuckDB returns naive datetime; assume UTC for service-local consistency.
            latest_run_utc = latest_run.replace(tzinfo=timezone.utc)
            age_seconds = int((now - latest_run_utc).total_seconds())

        return {
            "duckdb_path": self.duckdb_path,
            "tables": {
                "ai_insight_runs": int(run_count),
                "ai_customer_insights": int(insight_count),
                "ai_audience_recommendations": int(rec_count),
            },
            "latest_run_at": latest_run.isoformat() if latest_run else None,
            "latest_run_age_seconds": age_seconds,
        }


def get_ai_insights_store() -> AIInsightsStore:
    """Factory for AIInsightsStore."""
    return AIInsightsStore()

