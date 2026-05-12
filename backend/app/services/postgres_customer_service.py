"""Postgres-backed customer mart service.

Same API surface as RedshiftCustomerService. Reads from the local
warehouse-postgres container that mirrors the Redshift gold.* schema.
Wired in when settings.warehouse_mode == 'postgres'.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.customer import (
    CustomerAttributeResponse,
    CustomerListResponse,
    CustomerEventResponse,
    CustomerProfileDetail,
    CustomerProfileSummary,
    CustomerStats,
)

logger = get_logger(__name__)
settings = get_settings()


class PostgresCustomerService:
    """Customer list + stats backed by warehouse-postgres gold marts.

    Source tables (mirrored from Redshift via Meltano or DuckDB seeder):
    - gold.customer_unified_attr (primary customer row)
    - gold.order_line_fact (timeline derivation)
    """

    @contextmanager
    def _connect(self):
        if not settings.warehouse_postgres_host or not settings.warehouse_postgres_user:
            raise ValueError(
                "Postgres warehouse not configured. Set WAREHOUSE_POSTGRES_HOST, "
                "WAREHOUSE_POSTGRES_USER, WAREHOUSE_POSTGRES_DB, WAREHOUSE_POSTGRES_PASSWORD."
            )
        conn = psycopg2.connect(
            host=settings.warehouse_postgres_host,
            port=settings.warehouse_postgres_port,
            dbname=settings.warehouse_postgres_db,
            user=settings.warehouse_postgres_user,
            password=settings.warehouse_postgres_password,
            connect_timeout=30,
        )
        conn.set_session(readonly=True, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()

    def _estimate_row_count(self, schema: str, table: str) -> Optional[int]:
        """Fast row estimate via pg_stat_user_tables; None if unavailable."""
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT n_live_tup
                    FROM pg_stat_user_tables
                    WHERE schemaname = %s AND relname = %s
                    """,
                    (schema, table),
                )
                row = cur.fetchone()
                if not row or row[0] is None or row[0] <= 0:
                    return None
                return int(row[0])
        except Exception:
            return None

    def list_customers(
        self,
        search: Optional[str],
        page: int,
        page_size: int,
    ) -> CustomerListResponse:
        page = max(int(page), 1)
        page_size = max(min(int(page_size), 100), 1)
        offset = (page - 1) * page_size

        where = ""
        params: List[Any] = []
        if search:
            where = (
                "WHERE (LOWER(email) LIKE %s "
                "OR LOWER(phone) LIKE %s "
                "OR CAST(customer_id AS VARCHAR) LIKE %s)"
            )
            s = f"%{search.strip().lower()}%"
            params.extend([s, s, s])

        rows_sql = f"""
            SELECT
              customer_id,
              email,
              phone,
              country_code,
              state,
              revenue_last_52_weeks,
              orders_last_52_weeks,
              last_order_date
            FROM gold.customer_unified_attr
            {where}
            ORDER BY last_order_date DESC NULLS LAST
            LIMIT {page_size} OFFSET {offset}
        """
        total_sql = f"SELECT COUNT(*) FROM gold.customer_unified_attr {where}"

        with self._connect() as conn:
            cur = conn.cursor()
            if search:
                cur.execute(total_sql, tuple(params))
                total = int(cur.fetchone()[0] or 0)
            else:
                total = self._estimate_row_count("gold", "customer_unified_attr") or 0
            cur.execute(rows_sql, tuple(params))
            rows = cur.fetchall()

        customers: List[CustomerProfileSummary] = []
        for r in rows:
            customer_id = int(r[0])
            customers.append(
                CustomerProfileSummary(
                    id=customer_id,
                    external_id=str(customer_id),
                    email=r[1],
                    phone=r[2],
                    first_name=None,
                    last_name=None,
                    full_name=str(customer_id),
                    source_count=1,
                    first_seen_at=None,
                    last_seen_at=r[7],
                    last_synced_at=None,
                    lifetime_value=float(r[5]) if r[5] is not None else None,
                    total_orders=int(r[6]) if r[6] is not None else None,
                    city=r[4],
                    country=r[3],
                )
            )

        total_pages = max((total + page_size - 1) // page_size, 1) if total else 1
        return CustomerListResponse(
            customers=customers,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_stats(self) -> CustomerStats:
        total = self._estimate_row_count("gold", "customer_unified_attr")
        if total is None:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM gold.customer_unified_attr")
                total = int(cur.fetchone()[0] or 0)

        return CustomerStats(
            total_customers=total,
            customers_added_today=0,
            customers_added_this_week=0,
            customers_synced_today=0,
            avg_attributes_per_customer=0.0,
            top_sources=[],
        )

    def get_customer_detail(self, customer_id: int) -> Optional[CustomerProfileDetail]:
        sql = """
            SELECT *
            FROM gold.customer_unified_attr
            WHERE customer_id = %s
            LIMIT 1
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, (int(customer_id),))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]

        data = dict(zip(cols, row))
        now = datetime.now(timezone.utc)
        attrs: List[CustomerAttributeResponse] = []
        attr_id = 1
        for k, v in data.items():
            if k == "customer_id":
                continue
            attrs.append(
                CustomerAttributeResponse(
                    id=attr_id,
                    customer_id=int(customer_id),
                    attribute_name=k,
                    attribute_value=str(v) if v is not None else None,
                    attribute_type="string",
                    source_connection_id=None,
                    source_field=None,
                    source_name=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            attr_id += 1

        return CustomerProfileDetail(
            id=int(customer_id),
            external_id=str(customer_id),
            email=data.get("email"),
            phone=data.get("phone"),
            first_name=None,
            last_name=None,
            full_name=str(customer_id),
            source_count=1,
            first_seen_at=None,
            last_seen_at=data.get("last_order_date"),
            last_synced_at=None,
            lifetime_value=float(data["revenue_last_52_weeks"]) if data.get("revenue_last_52_weeks") is not None else None,
            total_orders=int(data["orders_last_52_weeks"]) if data.get("orders_last_52_weeks") is not None else None,
            city=data.get("state"),
            country=data.get("country_code"),
            attributes=attrs,
            recent_events=[],
            identities=[],
            created_at=now,
            updated_at=now,
        )

    def get_customer_timeline(
        self,
        customer_id: int,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[CustomerEventResponse]:
        """Minimal timeline derived from gold.order_line_fact."""
        limit = max(min(int(limit), 500), 1)

        sql = """
            SELECT
              order_id,
              MAX(order_processed_at_pst) AS occurred_at,
              SUM(line_revenue) AS revenue,
              SUM(qty) AS units,
              MAX(digital_vs_retail) AS channel
            FROM gold.order_line_fact
            WHERE customer_id = %s
            GROUP BY order_id
            ORDER BY occurred_at DESC NULLS LAST
            LIMIT %s
        """

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, (int(customer_id), limit))
            rows = cur.fetchall()

        now = datetime.now(timezone.utc)
        events: List[CustomerEventResponse] = []
        event_id = 1
        for order_id, occurred_at, revenue, units, channel in rows:
            if event_type and event_type != "order_placed":
                continue
            ts = occurred_at or now
            if isinstance(ts, datetime) and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            events.append(
                CustomerEventResponse(
                    id=event_id,
                    customer_id=int(customer_id),
                    event_type="order_placed",
                    event_category="commerce",
                    title=f"Order {order_id}",
                    description=None,
                    event_data={
                        "order_id": str(order_id),
                        "revenue": float(revenue) if revenue is not None else None,
                        "units": float(units) if units is not None else None,
                        "channel": str(channel) if channel is not None else None,
                    },
                    source_connection_id=None,
                    destination_connection_id=None,
                    sync_run_id=None,
                    occurred_at=ts,
                    source_name="Postgres (warehouse)",
                    destination_name=None,
                )
            )
            event_id += 1

        return events
