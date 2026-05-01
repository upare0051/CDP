"""C360 Redshift-backed services (schema + safe read-only query + PII handling)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import redshift_connector

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class QueryResult:
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    truncated: bool


def _normalize_table_ref(table_ref: str) -> str:
    """Normalize a SQL table reference into schema.table (lowercase) where possible."""
    cleaned = table_ref.strip().strip('"').strip()
    if " " in cleaned:
        cleaned = cleaned.split(" ", 1)[0]
    # remove catalog if present: catalog.schema.table -> schema.table
    parts = [p.strip('"') for p in cleaned.split(".") if p]
    if len(parts) >= 2:
        return f"{parts[-2].lower()}.{parts[-1].lower()}"
    return parts[-1].lower() if parts else ""


class C360RedshiftService:
    """
    Redshift-backed service for:
    - allowlisted schema introspection
    - safe query execution (SELECT/CTE only)
    - PII drop + deterministic anonymization (customer_id -> anon_id)
    - optional Presidio input/output redaction (when installed)
    """

    FORBIDDEN_SQL = re.compile(
        r"\b(insert|update|delete|drop|alter|create|replace|truncate|copy|unload|call|grant|revoke)\b",
        re.IGNORECASE,
    )
    TABLE_REF_SQL = re.compile(r"\b(?:from|join)\s+([a-zA-Z0-9_.\"]+)", re.IGNORECASE)

    def __init__(self):
        self.allowed_tables = {t.lower() for t in settings.c360_allowed_tables}
        self._drop_cols = {c.lower() for c in settings.c360_drop_cols}
        self._id_cols = {c.lower() for c in settings.c360_id_cols}
        self._anon_salt = settings.c360_anon_salt

    def _connect(self):
        if not settings.redshift_host or not settings.redshift_user or not settings.redshift_database:
            raise ValueError("Redshift not configured. Set REDSHIFT_HOST, REDSHIFT_USER, REDSHIFT_DATABASE (and password if needed).")

        return redshift_connector.connect(
            host=settings.redshift_host,
            port=settings.redshift_port,
            database=settings.redshift_database,
            user=settings.redshift_user,
            password=settings.redshift_password,
            ssl=settings.c360_redshift_ssl,
            timeout=settings.c360_query_timeout_seconds,
        )

    def _anonymize_id(self, value: Any) -> str:
        raw = f"{self._anon_salt}:{value}"
        return "anon_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    def anonymize_rows(self, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        out: List[Dict[str, Any]] = []
        for row in rows:
            clean: Dict[str, Any] = {}
            for k, v in row.items():
                k_lower = str(k).lower()
                if k_lower in self._drop_cols:
                    continue
                if k_lower in self._id_cols:
                    clean["anon_id"] = self._anonymize_id(v)
                    continue
                clean[k] = v
            out.append(clean)
        return out

    def redact_pii_text(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Best-effort PII redaction using Presidio (if installed).
        Falls back to no-op if Presidio or spaCy model is missing.
        """
        try:
            # Local import so backend still starts without presidio deps installed.
            import warnings

            warnings.filterwarnings("ignore", message=".*protected namespace.*")
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            from presidio_anonymizer.entities import OperatorConfig

            analyzer = AnalyzerEngine()
            anonymizer = AnonymizerEngine()
            pii_entities = ["PERSON", "EMAIL_ADDRESS"]
            operators = {e: OperatorConfig("replace", {"new_value": f"<{e}>"}) for e in pii_entities}

            results = analyzer.analyze(
                text=text,
                entities=pii_entities,
                language="en",
                score_threshold=0.4,
            )
            if not results:
                return text, []
            anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
            findings = [
                {"entity": r.entity_type, "score": round(r.score, 2), "start": r.start, "end": r.end}
                for r in results
            ]
            return anonymized.text, findings
        except Exception as e:
            logger.debug("Presidio redaction unavailable; continuing without it", error=str(e))
            return text, []

    def _validate_allowed_tables(self, sql: str) -> None:
        refs = self.TABLE_REF_SQL.findall(sql)
        normalized = {_normalize_table_ref(ref) for ref in refs if ref}
        disallowed = sorted(ref for ref in normalized if ref and ref not in self.allowed_tables)
        if disallowed:
            allowed = ", ".join(sorted(self.allowed_tables))
            blocked = ", ".join(disallowed)
            raise ValueError(f"Query references non-allowlisted tables ({blocked}). Allowed tables: {allowed}.")

    def get_allowlisted_schema(self) -> Dict[str, Any]:
        """
        Return column metadata for allowlisted tables from information_schema.
        """
        tables = sorted(self.allowed_tables)
        result_tables: List[Dict[str, Any]] = []

        with self._connect() as conn:
            cur = conn.cursor()
            for ref in tables:
                schema, table = ref.split(".", 1)
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, table),
                )
                cols = cur.fetchall()
                result_tables.append(
                    {
                        "schema": schema,
                        "table": table,
                        "table_reference": f"{schema}.{table}",
                        "columns": [{"name": c[0], "type": c[1]} for c in cols],
                    }
                )

        return {"database": settings.redshift_database, "tables": result_tables}

    def execute_read_query(self, sql: str, limit: int = 200) -> QueryResult:
        cleaned = sql.strip().rstrip(";")
        if not cleaned:
            raise ValueError("Query cannot be empty")
        if not (cleaned.lower().startswith("select") or cleaned.lower().startswith("with")):
            raise ValueError("Only SELECT/CTE queries are allowed")
        if self.FORBIDDEN_SQL.search(cleaned):
            raise ValueError("Query contains forbidden SQL keywords")
        self._validate_allowed_tables(cleaned)

        effective_limit = min(int(limit), int(settings.c360_max_rows))
        wrapped_sql = f"SELECT * FROM ({cleaned}) AS q LIMIT {effective_limit + 1}"

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(wrapped_sql)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description]

        truncated = len(rows) > effective_limit
        if truncated:
            rows = rows[:effective_limit]

        return QueryResult(
            columns=columns,
            rows=[list(r) for r in rows],
            row_count=len(rows),
            truncated=truncated,
        )

    def execute_read_query_dicts(self, sql: str, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Execute a safe query and return list-of-dicts, anonymized for PII.
        Intended for the Ask C360 endpoint.
        """
        result = self.execute_read_query(sql, limit=limit)
        raw_rows = [dict(zip(result.columns, r)) for r in result.rows]
        return self.anonymize_rows(raw_rows)

    def redact_results_json(self, rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Redact PII from JSON-serialized results (defense-in-depth).
        Returns (rows_after_redaction, was_redacted).
        """
        if not rows:
            return rows, False
        raw = json.dumps(rows, default=str)
        redacted, findings = self.redact_pii_text(raw)
        if not findings:
            return rows, False
        try:
            return json.loads(redacted), True
        except Exception:
            # If redaction broke JSON, just return the structured anonymized rows.
            return rows, True

