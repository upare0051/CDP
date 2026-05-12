# Cube semantic layer for cdp-main

Local Cube deployment that powers audience/segment queries for the cdp-main
Reverse ETL platform.

## Architecture

```
Redshift (prod) ──(Meltano: full + incremental)──► warehouse-postgres (5433)
                                                          │
                                                          ▼
                                                       cube-api (4000)
                                                          │
                                                          ▼
                                               cdp-main backend (FastAPI)
                                                          │
                                                          ▼
                                               Braze / Attentive (Reverse ETL)
```

- **warehouse-postgres** mirrors the Redshift CDP schemas (`gold`, `analytics`)
  so Cube can serve the demo without hitting prod.
- **cube-api** is built from the patched `alo-data-stack/cube` source.
- **cubestore** holds pre-aggregations.

## Prerequisites

- Docker + Docker Compose v2
- The patched Cube source checkout at `../alo-data-stack/cube` (or override
  via `ALO_CUBE_SOURCE` in `.env`)

## Quick start

From the cdp-main repo root:

```bash
# 1. Configure
cp cube/.env.example cube/.env
# edit cube/.env if needed

# 2. Build the custom Cube image and start the stack
#    (first build takes ~10-30 min; subsequent builds are cached)
docker compose -f docker-compose.yml -f cube/docker-compose.cube.yml up --build

# 3. Open the Cube playground
open http://localhost:4000
```

## Ports

| Service              | Port  | Notes                          |
|----------------------|-------|--------------------------------|
| app postgres         | 5432  | existing (cdp-main metadata)   |
| warehouse-postgres   | 5433  | new (CDP demo warehouse)       |
| cube-api / playground| 4000  | Cube REST + GraphQL + UI       |

## Data model

Cubes (`model/cubes/`) — one per gold table:

| Cube                          | Source table                          | Grain                  |
|-------------------------------|---------------------------------------|------------------------|
| `customer_dim`                | gold.customer_dim                     | 1 row / customer (hub) |
| `customer_address_dim`        | gold.customer_address_dim (current)   | 1 row / customer       |
| `customer_identifier_dim`     | gold.customer_identifier_dim (current)| 1 row / customer       |
| `customer_loyalty_dim`        | gold.customer_loyalty_dim (current)   | 1 row / customer       |
| `customer_contact_prefs_dim`  | gold.customer_contact_prefs_dim       | 1 row / customer       |
| `customer_geo_segment`        | gold.customer_geo_segment             | 1 row / customer       |
| `customer_rfm_fact`           | gold.customer_rfm_fact                | 1 row / customer       |
| `customer_unified_attr`       | gold.customer_unified_attr (wide)     | 1 row / customer       |
| `order_line_fact`             | gold.order_line_fact                  | 1 row / order line     |

SCD2 tables (`address`, `identifier`, `loyalty`) are filtered to `is_current = true`
inside the cube's `sql` so all customer-keyed joins are 1:1.

Views (`model/views/`):

- **`customer_unified`** — single-table view on the denormalized wide table.
  Fastest path for audience queries. Use this for Reverse ETL.
- **`customer_360`** — joined view across all dimensions + RFM + orders.
  Use when you need cross-cube aggregation.
- **`customer_marketing`** — curated subset for audience-building (identifiers,
  channel reachability, loyalty tier, RFM).

## Example audience queries

These hit the Cube REST API at `http://localhost:4000/cubejs-api/v1/load`.

**VIP customers (top revenue, last 52 weeks)**
```json
{
  "dimensions": ["customer_unified.customer_id", "customer_unified.email", "customer_unified.loyalty_tier_name"],
  "filters": [
    {"member": "customer_unified.revenue_last_52_weeks", "operator": "gte", "values": ["500"]},
    {"member": "customer_unified.email_subscribed", "operator": "equals", "values": ["true"]}
  ],
  "order": {"customer_unified.revenue_last_52_weeks": "desc"},
  "limit": 5000
}
```

**Lapsed buyers (no order in 90+ days, still email-reachable)**
```json
{
  "dimensions": ["customer_unified.customer_id", "customer_unified.email"],
  "filters": [
    {"member": "customer_unified.days_since_last_order", "operator": "gte", "values": ["90"]},
    {"member": "customer_unified.email_subscribed", "operator": "equals", "values": ["true"]},
    {"member": "customer_unified.email_hard_bounce", "operator": "equals", "values": ["false"]}
  ]
}
```

**Loyalty members by tier × geo segment**
```json
{
  "measures": ["customer_marketing.count", "customer_marketing.revenue_last_52_weeks_sum"],
  "dimensions": ["customer_marketing.loyalty_tier_name", "customer_marketing.digital_geo_segment"],
  "filters": [
    {"member": "customer_marketing.loyalty_enrolled", "operator": "equals", "values": ["true"]}
  ]
}
```

## Performance

Two complementary mechanisms power the demo:

1. **Postgres indexes** (`cube/scripts/warehouse_indexes.sql`) — serve
   row-level audience extraction (e.g. "give me customer_ids of all VIPs"
   for Reverse ETL). Apply with:
   ```bash
   docker exec -i cdp-main-warehouse-postgres-1 psql -U cdp -d cdp_warehouse \
     < cube/scripts/warehouse_indexes.sql
   ```
2. **Cube pre-aggregation** (`customer_unified_attr.marketing_rollup`) —
   materialized in Cube Store; serves aggregate slice-and-dice queries
   (count/revenue by tier, geo, channel). First build scans 25M rows
   (~1 min); subsequent hits are sub-second.

Measured latencies (25M-customer demo dataset):

| Query                         | Type        | Latency |
|-------------------------------|-------------|---------|
| `customer_unified_attr.count` | aggregate   | <100ms  |
| Loyalty tier × revenue rollup | aggregate   | <100ms  |
| Reachability by geo segment   | aggregate   | <100ms  |
| Top-N VIP audience extraction | row-level   | ~3s     |
| Lapsed email-reachable list   | row-level   | <1s     |

## Notes for Apple Silicon

- `cubejs/cubestore:latest` is amd64-only. Compose pulls
  `cubejs/cubestore:arm64v8` instead. Swap back on x86 hosts.
- The custom Cube image build from `${ALO_CUBE_SOURCE}` is wired but
  disabled (the prod Dockerfile doesn't `yarn build` the workspace, so
  cubejs-server can't require its subpackages). Compose currently uses
  upstream `cubejs/cube:latest`. To re-enable, add a `yarn build` step
  to `packages/cubejs-docker/latest.Dockerfile`.
- Host port `4000` is often held by other Cube dev containers, so this
  stack uses **`4001`** for the playground / REST API.

## Roadmap

- **Phase 1**: scaffold ✓
- **Phase 2**: Meltano tap from Redshift → `warehouse-postgres` (see `local-demo`
  branch in `~/alo-data-stack/alo-meltano`) ✓
- **Phase 3**: Cube models + audience views ✓
- **Phase 3.5**: Indexes + pre-aggregations for demo perf ✓
- **Phase 4** (next): FastAPI route in `backend/app/api/` that queries Cube
  REST API and feeds the existing Reverse ETL sync flow.

## Notes

- Cube only talks to `warehouse-postgres`. It never connects to Redshift.
- The patched Cube image carries Redshift compatibility fixes (timezone,
  identifier quoting, `pg_type.typcategory` fallback) — these don't affect
  this Postgres-only setup but ride along for future flexibility.
