"""Warehouse-backed data exploration service (schema, ERD hints, read-only SQL).

This service supports two execution modes:

- **redshift**: live, governed reads against allowlisted C360 marts
- **duckdb**: demo snapshot file materialized from Redshift (manual step)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import duckdb

from app.core.config import get_settings
from app.services.c360_service import C360RedshiftService

settings = get_settings()


@dataclass
class QueryResult:
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    truncated: bool


class ExplorerService:
    """
    Safe SQL runner + schema browser.

    This is intentionally restricted to the same allowlisted marts used by
    Reference / Ask C360.
    """

    FORBIDDEN_SQL = re.compile(
        r"\b(insert|update|delete|drop|alter|create|replace|truncate|copy|unload|call|grant|revoke)\b",
        re.IGNORECASE,
    )
    TABLE_REF_SQL = re.compile(r"\b(?:from|join)\s+([a-zA-Z0-9_.\"]+)", re.IGNORECASE)

    def __init__(self):
        self.mode = (settings.warehouse_mode or "redshift").lower()
        self.allowed_tables: Set[str] = {t.lower() for t in settings.c360_allowed_tables}
        self._c360 = C360RedshiftService()
        self._duckdb_path = settings.duckdb_path

    # -------------------------------------------------------------------------
    # Schema / ERD
    # -------------------------------------------------------------------------
    def get_schema_tree(self) -> Dict[str, Any]:
        if self.mode == "duckdb":
            return self._get_schema_tree_duckdb_snapshot()
        return self._get_schema_tree_redshift()

    def _get_schema_tree_redshift(self) -> Dict[str, Any]:
        meta = self._c360.get_allowlisted_schema()
        tables = []
        for t in meta["tables"]:
            tables.append(
                {
                    "catalog": meta["database"],
                    "schema": t["schema"],
                    "table": t["table"],
                    "table_reference": t["table_reference"],
                    "row_count": None,
                    "columns": t["columns"],
                }
            )
        return {"database": meta["database"], "tables": tables}

    def _get_schema_tree_duckdb_snapshot(self) -> Dict[str, Any]:
        path = Path(self._duckdb_path)
        if not path.exists():
            raise ValueError(
                f"DuckDB demo snapshot not found at {path}. Run the Redshift→DuckDB snapshot command first."
            )

        tables: List[Dict[str, Any]] = []
        with duckdb.connect(str(path), read_only=True) as conn:
            for ref in sorted(self.allowed_tables):
                schema, table = ref.split(".", 1)
                exists = conn.execute(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = ? AND table_name = ?
                    """,
                    [schema, table],
                ).fetchone()
                if not exists:
                    continue

                cols = conn.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = ? AND table_name = ?
                    ORDER BY ordinal_position
                    """,
                    [schema, table],
                ).fetchall()
                try:
                    row_count = conn.execute(f'SELECT count(*) FROM "{schema}"."{table}"').fetchone()[0]
                except Exception:
                    row_count = None

                tables.append(
                    {
                        "catalog": "duckdb_snapshot",
                        "schema": schema,
                        "table": table,
                        "table_reference": f"{schema}.{table}",
                        "row_count": row_count,
                        "columns": [{"name": c[0], "type": c[1]} for c in cols],
                    }
                )

        return {"database": "duckdb_snapshot", "tables": tables}

    def get_erd_hints(self) -> Dict[str, Any]:
        schema = self.get_schema_tree()
        edges = []
        table_names = {t["table"] for t in schema["tables"]}

        for t in schema["tables"]:
            for c in t["columns"]:
                name = c["name"]
                if name.endswith("_id"):
                    candidate = name[:-3]
                    candidates = [candidate, f"{candidate}s", f"{candidate}_dim", f"{candidate}_fact"]
                    to_table = next((x for x in candidates if x in table_names), None)
                    if to_table and to_table != t["table"]:
                        edges.append(
                            {
                                "from_table": t["table"],
                                "from_column": name,
                                "to_table": to_table,
                                "to_column": "id",
                            }
                        )

        return {
            "nodes": [{"table": t["table"]} for t in schema["tables"]],
            "edges": edges,
        }

    def get_team_views(self) -> Dict[str, Any]:
        # Explorer UI no longer depends on these legacy demo cards.
        return {"cards": [], "cs_priority_sample": [], "da_goal_breakdown": []}

    # -------------------------------------------------------------------------
    # Query execution
    # -------------------------------------------------------------------------
    def execute_read_query(self, sql: str, limit: int = 500) -> QueryResult:
        cleaned = sql.strip().rstrip(";")
        if not cleaned:
            raise ValueError("Query cannot be empty")
        if not (cleaned.lower().startswith("select") or cleaned.lower().startswith("with")):
            raise ValueError("Only SELECT/CTE queries are allowed")
        if self.FORBIDDEN_SQL.search(cleaned):
            raise ValueError("Query contains forbidden SQL keywords")

        self._validate_allowed_tables(cleaned)

        if self.mode == "duckdb":
            return self._execute_duckdb_snapshot_query(cleaned, limit=limit)

        # Redshift live
        result = self._c360.execute_read_query(cleaned, limit=limit)
        return QueryResult(
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            truncated=result.truncated,
        )

    def _execute_duckdb_snapshot_query(self, cleaned_sql: str, limit: int) -> QueryResult:
        path = Path(self._duckdb_path)
        if not path.exists():
            raise ValueError(
                f"DuckDB demo snapshot not found at {path}. Run the Redshift→DuckDB snapshot command first."
            )
        wrapped_sql = f"SELECT * FROM ({cleaned_sql}) AS q LIMIT {int(limit) + 1}"
        with duckdb.connect(str(path), read_only=True) as conn:
            result = conn.execute(wrapped_sql)
            columns = [d[0] for d in result.description]
            rows = result.fetchall()

        truncated = len(rows) > limit
        if truncated:
            rows = rows[:limit]

        return QueryResult(
            columns=columns,
            rows=[list(r) for r in rows],
            row_count=len(rows),
            truncated=truncated,
        )

    # -------------------------------------------------------------------------
    # Guardrails
    # -------------------------------------------------------------------------
    def _normalize_table_ref(self, table_ref: str) -> Optional[str]:
        cleaned = table_ref.strip().strip('"').strip()
        if not cleaned:
            return None
        if " " in cleaned:
            cleaned = cleaned.split(" ", 1)[0]
        cleaned = cleaned.strip('"')

        parts = [p.strip('"') for p in cleaned.split(".") if p]
        if len(parts) >= 2:
            return f"{parts[-2]}.{parts[-1]}".lower()
        return parts[-1].lower() if parts else None

    def _validate_allowed_tables(self, sql: str) -> None:
        refs = self.TABLE_REF_SQL.findall(sql)
        normalized = {self._normalize_table_ref(ref) for ref in refs if ref}
        normalized.discard(None)

        disallowed = sorted(ref for ref in normalized if ref not in self.allowed_tables)
        if disallowed:
            allowed = ", ".join(sorted(self.allowed_tables))
            blocked = ", ".join(disallowed)
            raise ValueError(f"Query references non-allowlisted tables ({blocked}). Allowed tables: {allowed}.")

