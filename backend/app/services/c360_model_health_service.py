"""C360 model health: upstream dbt models of customer_unified_attr + PST daily freshness.

Connection is sourced via `get_c360_service()` so this works against either
Redshift (prod) or the local Postgres warehouse, depending on warehouse_mode.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.c360_service import get_c360_service

logger = get_logger(__name__)
settings = get_settings()

PST = ZoneInfo("America/Los_Angeles")

# Prefer dbt bookkeeping columns, then common pipeline timestamps.
_WATERMARK_PRIORITY: Tuple[str, ...] = (
    "dbt_updated_at",
    "_dbt_updated_at",
    "updated_at",
    "loaded_at",
    "_loaded_at",
    "etl_loaded_at",
    "ingestion_timestamp",
    "created_at",
)

_IDENT_RE = re.compile(r"^[a-zA-Z0-9_]+$")

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "c360_upstream_customer_unified_attr.json"


def _is_br_rs_table(alias: str, name: str) -> bool:
    base = (alias or name or "").strip().lower()
    return base.startswith("br_rs_")


def _load_upstream_items() -> List[Dict[str, Any]]:
    if not _DATA_PATH.exists():
        raise FileNotFoundError(
            f"Missing upstream manifest data: {_DATA_PATH}. "
            "Run: python scripts/generate_c360_model_health_upstream.py"
        )
    with open(_DATA_PATH, encoding="utf-8") as f:
        payload = json.load(f)
    raw = list(payload.get("items") or [])
    return [it for it in raw if not _is_br_rs_table(str(it.get("alias") or ""), str(it.get("name") or ""))]


def _connect():
    """Return a context-manager-yielding DB connection for the active warehouse.

    Delegates to the C360 service factory so this picks Redshift or Postgres
    based on settings.warehouse_mode.
    """
    return get_c360_service()._connect()


def _validate_ident(name: str) -> str:
    if not name or not _IDENT_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _pick_watermark_column(conn, schema: str, table: str) -> Optional[str]:
    sch = _validate_ident(schema)
    tbl = _validate_ident(table)
    sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE lower(table_schema) = lower(%s)
          AND lower(table_name) = lower(%s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (sch, tbl))
        rows = {r[0].lower() for r in cur.fetchall()}
    for cand in _WATERMARK_PRIORITY:
        if cand.lower() in rows:
            return cand
    return None


def watermark_max_sql(schema: str, table: str, col: str) -> str:
    """SELECT used to compute the watermark (MAX of timestamp column)."""
    sch = _validate_ident(schema)
    tbl = _validate_ident(table)
    c = _validate_ident(col)
    return f'SELECT MAX("{c}") AS m FROM "{sch}"."{tbl}"'


def _fallback_watermark_sql(schema: str, table: str) -> str:
    """Shown when no priority column exists — safe identifiers only."""
    sch = _validate_ident(schema)
    tbl = _validate_ident(table)
    return (
        f'-- No column from the health probe priority list exists on this table.\n'
        f'-- Replace the column with a real refresh / ETL timestamp from your model.\n'
        f'SELECT MAX("updated_at") AS m FROM "{sch}"."{tbl}";'
    )


def _max_timestamp(conn, schema: str, table: str, col: str) -> Optional[datetime]:
    sql = watermark_max_sql(schema, table, col)
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout TO 15000")
        cur.execute(sql)
        row = cur.fetchone()
    if not row:
        return None
    v = row[0]
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def _to_pst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(PST)


def _status_for_last(last: Optional[datetime], start_today_pst: datetime) -> str:
    """
    ok    — last refresh occurred on or after start of current PST calendar day
    stale — known watermark exists but is before start of today PST
    unknown — no usable watermark column or query failed
    """
    if last is None:
        return "unknown"
    last_pst = _to_pst(last)
    if last_pst >= start_today_pst:
        return "ok"
    return "stale"


def _inspect_one(item: Dict[str, Any], start_today_pst: datetime) -> Dict[str, Any]:
    """Worker: own Redshift connection per task."""
    schema = (item.get("schema") or "").strip()
    alias = (item.get("alias") or item.get("name") or "").strip()
    if not schema or not alias:
        return {
            **item,
            "last_refreshed_at": None,
            "last_refreshed_at_pst": None,
            "watermark_column": None,
            "watermark_sql": None,
            "status": "unknown",
            "error": "missing schema or alias",
        }
    try:
        _validate_ident(schema)
        _validate_ident(alias)
    except ValueError as e:
        return {
            **item,
            "last_refreshed_at": None,
            "last_refreshed_at_pst": None,
            "watermark_column": None,
            "watermark_sql": None,
            "status": "unknown",
            "error": str(e),
        }

    err: Optional[str] = None
    last: Optional[datetime] = None
    wcol: Optional[str] = None
    sql_out: Optional[str] = None
    try:
        with _connect() as conn:
            wcol = _pick_watermark_column(conn, schema, alias)
            if wcol:
                sql_out = watermark_max_sql(schema, alias, wcol)
                last = _max_timestamp(conn, schema, alias, wcol)
            else:
                sql_out = _fallback_watermark_sql(schema, alias)
    except Exception as e:
        err = str(e)
        logger.warning("model_health row failed", schema=schema, table=alias, error=err)
        if sql_out is None:
            try:
                sql_out = _fallback_watermark_sql(schema, alias)
            except ValueError:
                sql_out = None

    last_pst_str = _to_pst(last).isoformat() if last else None
    return {
        **item,
        "table": alias,
        "watermark_column": wcol,
        "watermark_sql": sql_out,
        "last_refreshed_at": last.isoformat() if last else None,
        "last_refreshed_at_pst": last_pst_str,
        "status": _status_for_last(last, start_today_pst),
        "error": err,
    }


def get_model_health() -> Dict[str, Any]:
    now_pst = datetime.now(PST)
    start_today_pst = now_pst.replace(hour=0, minute=0, second=0, microsecond=0)

    terminal_item = {
        "unique_id": "model.terminal.customer_unified_attr",
        "resource_type": "model",
        "name": "customer_unified_attr",
        "schema": "gold",
        "alias": "customer_unified_attr",
        "relation_name": '"gold"."customer_unified_attr"',
    }

    upstream = _load_upstream_items()
    max_workers = min(10, max(1, settings.c360_model_health_max_workers))

    rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_inspect_one, it, start_today_pst): it for it in upstream}
        for fut in as_completed(futures):
            rows.append(fut.result())

    terminal = _inspect_one(terminal_item, start_today_pst)

    def _sort_key(r: Dict[str, Any]) -> Tuple[str, str]:
        return (r.get("schema") or "", r.get("alias") or r.get("name") or "")

    rows.sort(key=_sort_key)

    ok_n = sum(1 for r in rows if r.get("status") == "ok")
    stale_n = sum(1 for r in rows if r.get("status") == "stale")
    unk_n = sum(1 for r in rows if r.get("status") == "unknown")

    return {
        "timezone": "America/Los_Angeles",
        "as_of_pst": now_pst.isoformat(),
        "start_of_today_pst": start_today_pst.isoformat(),
        "terminal_thoughtspot_table": terminal,
        "upstream": rows,
        "summary": {
            "upstream_total": len(rows),
            "ok": ok_n,
            "stale": stale_n,
            "unknown": unk_n,
        },
    }
