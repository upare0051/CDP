#!/usr/bin/env python3
"""
Materialize a demo-safe DuckDB snapshot from Redshift.

This is a manual workflow (option B):

- Engineers use Redshift live at runtime (WAREHOUSE_MODE=redshift)
- For local demos, generate a DuckDB file and run with WAREHOUSE_MODE=duckdb

The snapshot uses the same allowlisted tables as C360/Ask/Reference and
preserves schema names (e.g. gold.customer_rfm_fact).
"""

from __future__ import annotations

import argparse
import sys
import socket
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Optional

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.config import get_settings
from app.services.c360_service import C360RedshiftService

try:
    import connectorx as cx  # type: ignore
except Exception:  # pragma: no cover
    cx = None


def _iter_chunks(rows: List[Tuple[Any, ...]], chunk_size: int) -> Iterable[List[Tuple[Any, ...]]]:
    for i in range(0, len(rows), chunk_size):
        yield rows[i : i + chunk_size]

def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _duckdb_type(
    redshift_data_type: str,
    numeric_precision: Optional[int],
    numeric_scale: Optional[int],
    char_len: Optional[int],
) -> str:
    t = (redshift_data_type or "").lower()

    # Numeric/decimal: choose a safe precision; Redshift supports up to 38.
    if t in {"numeric", "decimal"}:
        scale = int(numeric_scale or 0)
        # Use max precision to avoid overflows from sampling/inference.
        return f"DECIMAL(38,{min(scale, 37)})"

    if t in {"real", "float4"}:
        return "REAL"
    if t in {"double precision", "float8"}:
        return "DOUBLE"
    if t in {"smallint", "int2"}:
        return "SMALLINT"
    if t in {"integer", "int", "int4"}:
        return "INTEGER"
    if t in {"bigint", "int8"}:
        return "BIGINT"
    if t in {"boolean", "bool"}:
        return "BOOLEAN"
    if "timestamp" in t:
        return "TIMESTAMP"
    if t == "date":
        return "DATE"
    if t in {"time", "timetz"}:
        return "TIME"

    # Semi-structured / unknown: store as text.
    if t in {"super", "variant", "json"}:
        return "VARCHAR"

    if t in {"character varying", "varchar", "character", "char", "text"}:
        # DuckDB doesn't require length; keep it flexible.
        return "VARCHAR"

    # Fallback
    return "VARCHAR"


def _fetch_redshift_columns(
    cursor,
    schema: str,
    table: str,
) -> List[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT
          column_name,
          data_type,
          numeric_precision,
          numeric_scale,
          character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )
    out: List[Dict[str, Any]] = []
    for row in cursor.fetchall():
        out.append(
            {
                "name": row[0],
                "data_type": row[1],
                "numeric_precision": row[2],
                "numeric_scale": row[3],
                "char_len": row[4],
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot allowlisted Redshift tables into a DuckDB file.")
    parser.add_argument(
        "--out",
        default="data/demo/activationos_demo.duckdb",
        help="Output DuckDB file path (relative to repo root by default).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="If the output DuckDB already exists, keep it and only copy missing/empty tables.",
    )
    parser.add_argument(
        "--max-rows-per-table",
        type=int,
        default=5000,
        help="Max rows to copy per table. Use 0 to copy all rows.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2000,
        help="Insert chunk size for DuckDB writes.",
    )
    parser.add_argument(
        "--use-connectorx",
        action="store_true",
        help="Use connectorx (Arrow/parallel read) when available for faster snapshots.",
    )
    parser.add_argument("--redshift-host", default=None, help="Override Redshift host (default: from .env/settings).")
    parser.add_argument("--redshift-port", type=int, default=None, help="Override Redshift port (default: from .env/settings).")
    args = parser.parse_args()

    settings = get_settings()
    if args.redshift_host:
        settings.redshift_host = args.redshift_host
    if args.redshift_port:
        settings.redshift_port = args.redshift_port
    if not settings.redshift_host or not settings.redshift_user or not settings.redshift_database:
        raise SystemExit(
            "Redshift not configured. Set REDSHIFT_HOST, REDSHIFT_USER, REDSHIFT_DATABASE (and password if needed)."
        )

    host = settings.redshift_host
    port = int(settings.redshift_port or 5439)
    print(f"Redshift target: host={host} port={port} db={settings.redshift_database} user={settings.redshift_user}")
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError as e:
        raise SystemExit(
            f"Cannot connect to Redshift at {host}:{port} ({e}).\n"
            "If you're using an SSH tunnel, start it first (localhost:10005 must be reachable)."
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    c360 = C360RedshiftService()
    schema_meta: Dict[str, Any] = c360.get_allowlisted_schema()
    tables: List[Dict[str, Any]] = schema_meta["tables"]

    if out_path.exists() and not args.resume:
        out_path.unlink()

    limit_n = int(args.max_rows_per_table)
    limit_sql = "" if limit_n <= 0 else f" LIMIT {limit_n}"

    print(f"Writing DuckDB snapshot to: {out_path}")
    print(f"Tables: {len(tables)}  | max_rows_per_table={'ALL' if limit_n <= 0 else limit_n}")

    with duckdb.connect(str(out_path)) as dconn:
        with c360._connect() as rconn:  # intentional: reuse configured connector/SSL/timeout
            rcur = rconn.cursor()

            # Known SCD2 snapshot tables (current rows only for demo snapshots)
            scd2_tables = {
                ("gold", "customer_address_dim"),
                ("gold", "customer_identifier_dim"),
                ("gold", "customer_loyalty_dim"),
            }
            # Inline literal (avoid driver/connectorx placeholder issues)
            scd2_current_predicate = "effective_to = CAST('9999-12-31' AS TIMESTAMP)"

            for t in tables:
                schema = t["schema"]
                table = t["table"]

                dconn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                if args.resume:
                    # If table exists and already has rows, skip it.
                    try:
                        existing = dconn.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"').fetchone()
                        if existing:
                            existing_rows = int(existing[0] or 0)
                            if existing_rows > 0:
                                print(f"- {schema}.{table}: already present ({existing_rows} rows); skipping", flush=True)
                                continue
                            # Exists but empty/partial: drop and recreate.
                            dconn.execute(f'DROP TABLE IF EXISTS "{schema}"."{table}"')
                    except Exception:
                        # Table doesn't exist yet (or schema missing) — proceed to create.
                        pass
                else:
                    dconn.execute(f'DROP TABLE IF EXISTS "{schema}"."{table}"')

                col_meta = _fetch_redshift_columns(rcur, schema=schema, table=table)
                if not col_meta:
                    print("  no columns found; skipping", flush=True)
                    continue

                cols = [c["name"] for c in col_meta]
                has_effective_to = any((c["name"] or "").lower() == "effective_to" for c in col_meta)
                is_scd2 = (schema, table) in scd2_tables or (has_effective_to and table.endswith("_dim"))

                quoted_cols = ", ".join([_quote_ident(c) for c in cols])

                col_defs_parts = [
                    f'{_quote_ident(c["name"])} {_duckdb_type(c["data_type"], c["numeric_precision"], c["numeric_scale"], c["char_len"])}'
                    for c in col_meta
                ]
                # For SCD2 tables, add an explicit is_current flag to simplify demo queries.
                if is_scd2:
                    col_defs_parts.append('"is_current" BOOLEAN')
                col_defs = ", ".join(col_defs_parts)
                dconn.execute(f'CREATE TABLE "{schema}"."{table}" ({col_defs})')

                where_sql = ""
                if is_scd2 and has_effective_to:
                    where_sql = f" WHERE {scd2_current_predicate}"

                select_cols_sql = quoted_cols
                insert_cols = cols[:]
                if is_scd2:
                    # Only copy current rows; mark is_current=true for copied rows.
                    select_cols_sql = f"{quoted_cols}, TRUE AS is_current"
                    insert_cols.append("is_current")

                sql = f'SELECT {select_cols_sql} FROM "{schema}"."{table}"{where_sql}{limit_sql}'

                print(f"- {schema}.{table}: fetching…", flush=True)
                col_list = ", ".join([_quote_ident(c) for c in insert_cols])
                placeholders = ", ".join(["?"] * len(insert_cols))
                insert_sql = f'INSERT INTO "{schema}"."{table}" ({col_list}) VALUES ({placeholders})'
                copied = 0
                try:
                    used_fast_path = False
                    if args.use_connectorx and cx is not None and settings.redshift_password:
                        # connectorx expects a URI. We keep SSL off by default (tunnel).
                        # Note: database name maps to the "dbname" portion.
                        rs_uri = (
                            f"redshift://{settings.redshift_user}:{settings.redshift_password}"
                            f"@{host}:{port}/{settings.redshift_database}"
                        )
                        arrow_tbl = cx.read_sql(rs_uri, sql, return_type="arrow")
                        dconn.register("_cx_tmp", arrow_tbl)
                        dconn.execute(f'INSERT INTO "{schema}"."{table}" SELECT * FROM _cx_tmp')
                        dconn.unregister("_cx_tmp")
                        copied = int(getattr(arrow_tbl, "num_rows", 0) or 0)
                        used_fast_path = True

                    if not used_fast_path:
                        rcur.execute(sql)
                        while True:
                            chunk = rcur.fetchmany(args.chunk_size)
                            if not chunk:
                                break
                            dconn.executemany(insert_sql, chunk)
                            copied += len(chunk)
                except Exception as e:
                    # If a relation is missing or permissions are insufficient, skip and continue.
                    print(f"  failed to copy {schema}.{table}: {e}", flush=True)
                    # If we partially created the table during resume, drop it so reruns can retry cleanly.
                    try:
                        dconn.execute(f'DROP TABLE IF EXISTS "{schema}"."{table}"')
                    except Exception:
                        pass
                    continue

                print(f"  copied {copied} rows", flush=True)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

