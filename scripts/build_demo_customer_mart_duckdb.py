#!/usr/bin/env python3
"""
Build a small DuckDB file with gold.customer_unified_attr and gold.order_line_fact
for leadership demos (fast customer search without Redshift).

Usage (from repo root, use the project venv):
  .venv/bin/python scripts/build_demo_customer_mart_duckdb.py
  .venv/bin/python scripts/build_demo_customer_mart_duckdb.py --out data/demo/customer_mart.duckdb

Does not connect to Redshift.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=Path,
        default=root / "data" / "demo" / "customer_mart.duckdb",
        help="Output DuckDB path",
    )
    args = ap.parse_args()
    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    con = duckdb.connect(str(out))
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")

    con.execute(
        """
        CREATE TABLE gold.customer_unified_attr (
            customer_id BIGINT,
            email VARCHAR,
            phone VARCHAR,
            country_code VARCHAR,
            state VARCHAR,
            revenue_last_52_weeks DOUBLE,
            orders_last_52_weeks BIGINT,
            last_order_date TIMESTAMP
        )
        """
    )

    con.execute(
        """
        CREATE TABLE gold.order_line_fact (
            order_id VARCHAR,
            customer_id BIGINT,
            order_processed_at_pst TIMESTAMP,
            line_revenue DOUBLE,
            qty DOUBLE,
            digital_vs_retail VARCHAR
        )
        """
    )

    rng = __import__("random").Random(42)
    base = date.today() - timedelta(days=400)
    rows_attr = []
    rows_order = []
    for i in range(1, 201):
        cid = i
        rev = round(rng.uniform(50, 5000), 2)
        orders = rng.randint(1, 40)
        days_ago = rng.randint(0, 180)
        last_order = datetime.combine(base + timedelta(days=rng.randint(0, 300)), datetime.min.time())
        rows_attr.append(
            (
                cid,
                f"user{cid}@demo.aloyoga.com",
                f"555-{cid:04d}",
                "US",
                rng.choice(["CA", "NY", "TX", "FL", "WA"]),
                rev,
                orders,
                last_order,
            )
        )
        for _o in range(min(orders, 5)):
            oid = f"ORD-{cid}-{rng.randint(1000, 9999)}"
            rows_order.append(
                (
                    oid,
                    cid,
                    datetime.now(timezone.utc) - timedelta(days=days_ago + _o),
                    round(rng.uniform(20, 800), 2),
                    float(rng.randint(1, 3)),
                    rng.choice(["digital", "retail"]),
                )
            )

    for row in rows_attr:
        con.execute(
            "INSERT INTO gold.customer_unified_attr VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            list(row),
        )
    for row in rows_order:
        con.execute(
            "INSERT INTO gold.order_line_fact VALUES (?, ?, ?, ?, ?, ?)",
            list(row),
        )
    con.close()
    print(f"Wrote {out} ({len(rows_attr)} customers, {len(rows_order)} order lines)")


if __name__ == "__main__":
    main()
