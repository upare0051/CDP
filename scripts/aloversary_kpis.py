#!/usr/bin/env python3
"""Compute Aloversary KPIs locally from parquet/CSV snapshots of Shopify GraphQL bronze.

Uses **Polars** for fast single-machine aggregates (often what people mean by "Polaris"-style local compute).

**Do not use `br_rs_*`** — snapshot these relations from Redshift (or wherever bronze lands):

  - bronze.br_gq_shopify_order
  - bronze.br_gq_shopify_order_line_item  (optional, for units / line-derived revenue sanity)
  - bronze.br_gq_shopify_transaction     (optional, for capture/sale counts)

Redshift exports (example — adjust bucket / IAM; columns must match your table):

    UNLOAD ($$
      SELECT order_id, customer_id, processed_at, created_at, cancelled_at,
             test, financial_status, total_price_usd, source_name_adj
      FROM bronze.br_gq_shopify_order
      WHERE processed_at >= '<history_start>' AND processed_at < '<event_end>'
    $$)
    TO 's3://your-bucket/aloversary/br_gq_shopify_order_'
    IAM_ROLE default PARALLEL ON ALLOWOVERWRITE HEADER PARQUET;

For **new customers (first purchase in window)** you need enough order history that
`MIN(processed_at)` per customer is correct (include pre-event orders).

Usage::

    pip install -r scripts/aloversary-requirements.txt
    python scripts/aloversary_kpis.py --orders data/aloversary/br_gq_shopify_order.parquet \\
        --event-start 2026-05-01 --event-days 7

    python scripts/aloversary_kpis.py --demo
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import polars as pl


DEFAULT_PAID_STATUSES = (
    "paid",
    "partially_paid",
    "partially_refunded",
    "authorized",
)
DEFAULT_TRANS_KINDS = ("sale", "capture")
DEFAULT_TRANS_SUCCESS = ("success",)


def _scan(path: Path) -> pl.LazyFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    suf = path.suffix.lower()
    if suf == ".parquet":
        return pl.scan_parquet(path)
    if suf == ".csv":
        return pl.scan_csv(path, try_parse_dates=True)
    raise ValueError(f"Unsupported file type: {path} (use .parquet or .csv)")


def _normalize_ts(df: pl.LazyFrame, cols: tuple[str, ...]) -> pl.LazyFrame:
    exprs = []
    names = df.collect_schema().names()
    for c in cols:
        if c not in names:
            continue
        dt = df.collect_schema()[c]
        stringish = dt in (pl.Utf8, pl.String)
        if stringish:
            exprs.append(
                pl.col(c).str.to_datetime(strict=False, time_zone="UTC").alias(c)
            )
        else:
            exprs.append(pl.col(c).cast(pl.Datetime(time_zone="UTC"), strict=False).alias(c))
    return df.with_columns(exprs) if exprs else df


def _normalize_bool(df: pl.LazyFrame, col: str) -> pl.LazyFrame:
    sch = df.collect_schema()
    if col not in sch.names():
        return df
    dt = sch[col]
    if dt == pl.Boolean:
        return df
    return df.with_columns(
        pl.when(pl.col(col).is_null())
        .then(None)
        .when(pl.col(col).cast(pl.Utf8).str.to_lowercase().is_in(["true", "1", "t", "yes"]))
        .then(True)
        .when(pl.col(col).cast(pl.Utf8).str.to_lowercase().is_in(["false", "0", "f", "no"]))
        .then(False)
        .otherwise(pl.col(col).cast(pl.Boolean, strict=False))
        .alias(col)
    )


def _schema_names(lf: pl.LazyFrame) -> set[str]:
    return set(lf.collect_schema().names())


def qualifying_orders_lazy(
    orders: pl.LazyFrame,
    event_start,
    event_end,
    *,
    paid_statuses: tuple[str, ...] | None,
) -> pl.LazyFrame:
    orders = _normalize_ts(orders, ("processed_at", "created_at", "cancelled_at"))
    orders = _normalize_bool(orders, "test")
    names = _schema_names(orders)
    filt = (
        (pl.col("processed_at").is_not_null())
        & (pl.col("processed_at") >= pl.lit(event_start))
        & (pl.col("processed_at") < pl.lit(event_end))
        & (pl.col("cancelled_at").is_null())
    )
    if "test" in names:
        filt = filt & (~pl.col("test").fill_null(False))
    if paid_statuses and "financial_status" in names:
        filt = filt & (
            pl.col("financial_status")
            .str.to_lowercase()
            .fill_null("")
            .is_in([s.lower() for s in paid_statuses])
        )
    return orders.filter(filt)


def compute_kpis(
    orders_lazy: pl.LazyFrame,
    *,
    lines_lazy: pl.LazyFrame | None,
    transactions_lazy: pl.LazyFrame | None,
    event_start,
    event_end,
    paid_statuses: tuple[str, ...] | None,
    trans_kinds: tuple[str, ...],
    trans_success: tuple[str, ...],
) -> dict[str, Any]:
    fo = qualifying_orders_lazy(
        orders_lazy, event_start, event_end, paid_statuses=paid_statuses
    )

    kpis: dict[str, Any] = {}

    fo_names = _schema_names(fo)
    agg = fo.select(
        [
            pl.col("customer_id").n_unique().alias("purchasing_customers"),
            pl.len().alias("orders_in_window"),
        ]
    ).collect()
    kpis["purchasing_customers"] = int(agg["purchasing_customers"][0])
    kpis["orders"] = int(agg["orders_in_window"][0])

    revenue_col = (
        "total_price_usd"
        if "total_price_usd" in fo_names
        else ("total_price" if "total_price" in fo_names else None)
    )
    if revenue_col:
        rev = fo.select(pl.col(revenue_col).sum()).collect()[revenue_col][0]
        kpis["gmv_orders"] = float(rev or 0.0)
        if kpis["orders"]:
            kpis["aov"] = kpis["gmv_orders"] / kpis["orders"]
        else:
            kpis["aov"] = None
    else:
        kpis["gmv_orders"] = None
        kpis["aov"] = None

    oh = _normalize_ts(orders_lazy, ("processed_at", "cancelled_at"))
    oh = _normalize_bool(oh, "test")
    if "customer_id" in _schema_names(oh):
        h = oh.filter(pl.col("cancelled_at").is_null())
        if "test" in _schema_names(h):
            h = h.filter(~pl.col("test").fill_null(False))
        first_purchase = (
            h.filter(pl.col("customer_id").is_not_null())
            .group_by("customer_id")
            .agg(pl.col("processed_at").min().alias("first_processed_at"))
        )
        np = (
            first_purchase.filter(
                (pl.col("first_processed_at") >= pl.lit(event_start))
                & (pl.col("first_processed_at") < pl.lit(event_end))
            )
            .select(pl.len())
            .collect()[0, 0]
        )
        kpis["new_customers_first_purchase_in_window"] = int(np)
    else:
        kpis["new_customers_first_purchase_in_window"] = None

    if lines_lazy is not None:
        li = _normalize_ts(lines_lazy, ("updated_at",))
        lf = qualifying_orders_lazy(
            orders_lazy, event_start, event_end, paid_statuses=paid_statuses
        )
        li_cols = ["order_id"] + (["quantity"] if "quantity" in _schema_names(li) else [])
        joined_mat = lf.select("order_id").join(li.select(li_cols), on="order_id", how="inner").collect()
        kpis["line_rows"] = joined_mat.height
        if "quantity" in joined_mat.columns:
            kpis["units_sold"] = int(joined_mat["quantity"].sum() or 0)
        else:
            kpis["units_sold"] = None

    if transactions_lazy is not None:
        tx = _normalize_ts(transactions_lazy, ("processed_at", "created_at"))
        tx = _normalize_bool(tx, "test")
        fo_ids = fo.select("order_id").unique()
        tx = tx.join(fo_ids, on="order_id", how="inner")
        tn = _schema_names(tx)
        if "kind" in tn:
            tx = tx.filter(
                pl.col("kind").str.to_lowercase().is_in([k.lower() for k in trans_kinds])
            )
        if "status" in tn:
            tx = tx.filter(
                pl.col("status").str.to_lowercase().is_in([s.lower() for s in trans_success])
            )
        if "test" in _schema_names(tx):
            tx = tx.filter(~pl.col("test").fill_null(False))
        cnt = tx.select(pl.len()).collect()[0, 0]
        kpis["transactions_success_in_window"] = int(cnt)

    kpis["_meta"] = {
        "event_start_utc": str(event_start),
        "event_end_utc_exclusive": str(event_end),
        "paid_status_filter": list(paid_statuses) if paid_statuses else None,
        "source_tables": "bronze.br_gq_shopify_* (not br_rs_*)",
    }
    return kpis


def _demo_dfs() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    orders = pl.DataFrame(
        {
            "order_id": [1, 2, 3, 4],
            "customer_id": [100, 200, 100, 300],
            "processed_at": [
                "2026-04-15T18:00:00Z",
                "2026-05-02T12:00:00Z",
                "2026-05-03T09:00:00Z",
                "2026-05-03T15:00:00Z",
            ],
            "created_at": [
                "2026-04-15T17:59:00Z",
                "2026-05-02T11:58:00Z",
                "2026-05-03T09:01:00Z",
                "2026-05-03T14:58:00Z",
            ],
            "cancelled_at": [None, None, None, None],
            "test": [False, False, False, False],
            "financial_status": ["paid"] * 4,
            "total_price_usd": [50.0, 120.0, 75.5, 200.0],
            "source_name_adj": ["web", "web", "retail", "web"],
        }
    ).with_columns(
        pl.col("processed_at").str.to_datetime(time_zone="UTC"),
        pl.col("created_at").str.to_datetime(time_zone="UTC"),
        pl.lit(None).cast(pl.Datetime(time_zone="UTC")).alias("cancelled_at"),
    )
    lines = pl.DataFrame(
        {
            "order_id": [2, 2, 3, 4],
            "line_items_id": [1, 2, 3, 4],
            "quantity": [1, 2, 1, 3],
        }
    )
    txs = pl.DataFrame(
        {
            "transaction_id": [10, 11, 12, 13],
            "order_id": [2, 2, 3, 4],
            "kind": ["sale", "capture", "sale", "sale"],
            "status": ["success"] * 4,
            "test": [False] * 4,
            "processed_at": [
                "2026-05-02T12:00:01Z",
                "2026-05-02T12:00:05Z",
                "2026-05-03T09:05:00Z",
                "2026-05-03T15:02:00Z",
            ],
        }
    ).with_columns(pl.col("processed_at").str.to_datetime(time_zone="UTC"))
    return orders, lines, txs


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--orders", type=Path, help="Parquet or CSV snapshot of bronze.br_gq_shopify_order")
    p.add_argument("--lines", type=Path, help="Optional: bronze.br_gq_shopify_order_line_item")
    p.add_argument("--transactions", type=Path, help="Optional: bronze.br_gq_shopify_transaction")
    p.add_argument("--event-start", type=str, required=False, help="ISO date/datetime UTC, e.g. 2026-05-01")
    p.add_argument("--event-days", type=int, default=7)
    p.add_argument(
        "--no-financial-filter",
        action="store_true",
        help="Do not filter orders by financial_status (not recommended)",
    )
    p.add_argument("--demo", action="store_true", help="Run on synthetic bronze-shaped data")
    args = p.parse_args(argv)

    if args.demo:
        o_df, li_df, tx_df = _demo_dfs()
        from datetime import datetime as dt_module

        event_start = dt_module.fromisoformat("2026-05-01T00:00:00+00:00")
        event_end = event_start + timedelta(days=args.event_days)
        paid = None if args.no_financial_filter else DEFAULT_PAID_STATUSES
        kpis = compute_kpis(
            o_df.lazy(),
            lines_lazy=li_df.lazy(),
            transactions_lazy=tx_df.lazy(),
            event_start=event_start,
            event_end=event_end,
            paid_statuses=paid,
            trans_kinds=DEFAULT_TRANS_KINDS,
            trans_success=DEFAULT_TRANS_SUCCESS,
        )
        print(json.dumps(kpis, indent=2, default=str))
        return 0

    if not args.orders or not args.event_start:
        p.error("--orders and --event-start are required unless --demo is set.")

    orders_lf = _scan(args.orders)
    lines_lf = _scan(args.lines) if args.lines else None
    tx_lf = _scan(args.transactions) if args.transactions else None

    from datetime import datetime as dt_module

    try:
        event_start = dt_module.fromisoformat(args.event_start.replace("Z", "+00:00"))
    except ValueError:
        event_start = dt_module.fromisoformat(args.event_start + "T00:00:00+00:00")
    event_end = event_start + timedelta(days=args.event_days)

    paid = None if args.no_financial_filter else DEFAULT_PAID_STATUSES
    kpis = compute_kpis(
        orders_lf,
        lines_lazy=lines_lf,
        transactions_lazy=tx_lf,
        event_start=event_start,
        event_end=event_end,
        paid_statuses=paid,
        trans_kinds=DEFAULT_TRANS_KINDS,
        trans_success=DEFAULT_TRANS_SUCCESS,
    )
    print(json.dumps(kpis, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
