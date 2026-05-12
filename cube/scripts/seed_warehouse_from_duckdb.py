"""Seed warehouse-postgres with gold.* tables from cdp-main's DuckDB demo files.

Uses DuckDB's native `postgres` extension for efficient bulk transfer
(`CREATE TABLE pg.gold.X AS SELECT * FROM gold.X`).

Source files:
    cdp-main/data/demo/activationos_demo_2.duckdb  -> 8 customer dim/fact tables
    cdp-main/data/demo/customer_mart.duckdb        -> order_line_fact

Run:
    .venv/bin/python cube/scripts/seed_warehouse_from_duckdb.py
"""

from __future__ import annotations

import os
import sys
import time

import duckdb

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEMO_DIR = os.path.join(REPO_ROOT, 'data', 'demo')

SOURCES = [
    (
        os.path.join(DEMO_DIR, 'activationos_demo_2.duckdb'),
        [
            'gold.customer_dim',
            'gold.customer_address_dim',
            'gold.customer_contact_prefs_dim',
            'gold.customer_identifier_dim',
            'gold.customer_loyalty_dim',
            'gold.customer_geo_segment',
            'gold.customer_rfm_fact',
            'gold.customer_unified_attr',
        ],
    ),
    (
        os.path.join(DEMO_DIR, 'customer_mart.duckdb'),
        ['gold.order_line_fact'],
    ),
]

PG_CONN = (
    f"host={os.environ.get('WAREHOUSE_POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('WAREHOUSE_POSTGRES_PORT', '5433')} "
    f"dbname={os.environ.get('WAREHOUSE_POSTGRES_DB', 'cdp_warehouse')} "
    f"user={os.environ.get('WAREHOUSE_POSTGRES_USER', 'cdp')} "
    f"password={os.environ.get('WAREHOUSE_POSTGRES_PASSWORD', 'cdp')}"
)


def seed():
    print(f'Postgres conn: {PG_CONN.replace(os.environ.get("WAREHOUSE_POSTGRES_PASSWORD", "cdp"), "***")}')

    # Use a writable in-memory DuckDB as the orchestrator so we can attach
    # the demo file read-only and Postgres read-write.
    con = duckdb.connect(':memory:')
    con.execute("INSTALL postgres; LOAD postgres;")
    con.execute(f"ATTACH '{PG_CONN}' AS pg (TYPE postgres);")
    con.execute("CREATE SCHEMA IF NOT EXISTS pg.gold;")

    for db_path, tables in SOURCES:
        if not os.path.exists(db_path):
            print(f'FATAL: {db_path} not found', file=sys.stderr)
            sys.exit(1)

        print(f'\n--- {db_path} ---')
        con.execute(f"ATTACH '{db_path}' AS demo (READ_ONLY);")
        try:
            for fq in tables:
                schema, name = fq.split('.', 1)
                t0 = time.time()
                print(f'  {fq} ... ', end='', flush=True)
                try:
                    con.execute(f'DROP TABLE IF EXISTS pg.{schema}.{name};')
                    con.execute(f'CREATE TABLE pg.{schema}.{name} AS SELECT * FROM demo.{fq};')
                    cnt = con.execute(f'SELECT count(*) FROM pg.{schema}.{name}').fetchone()[0]
                    print(f'{cnt:>12,} rows in {time.time()-t0:.1f}s')
                except Exception as e:
                    print(f'ERROR: {e}')
                    raise
        finally:
            con.execute("DETACH demo;")

    con.close()
    print('\nSeed complete.')


if __name__ == '__main__':
    seed()
