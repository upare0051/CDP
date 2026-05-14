# Warehouse, Redshift dev, CRM patterns, and Airflow

This doc matches how **cdp-main** is used today and the **two downstream patterns** we want to keep: **tables in Redshift** (CRM reads tables) vs **API delivery** (e.g. Braze REST).

---

## 1. Redshift dev tunnel (`127.0.0.1:10005`)

- **Dev Redshift** is typically reached through an **SSH tunnel** mapped to **`127.0.0.1:10005`** (same as `localhost:10005`).
- In repo-root **`.env`** (see `env.example`):

  ```bash
  REDSHIFT_HOST=127.0.0.1
  REDSHIFT_PORT=10005
  REDSHIFT_USER=...
  REDSHIFT_PASSWORD=...
  REDSHIFT_DATABASE=...
  ```

- **Snapshot script** (`scripts/snapshot_redshift_to_duckdb.py`) validates connectivity at startup; if the tunnel is down, fix the tunnel before snapshotting.

`127.0.0.1` and `localhost` are interchangeable for the tunnel listen address; pick one and keep `.env` consistent.

---

## 2. `warehouse-postgres` and `gold.*` — **fresh data from Redshift**

**Important:** Files under `data/demo/*.duckdb` are **snapshots**. They go **stale** relative to live **Redshift `gold.*`**. For E2E tests that must match **current** Redshift dev marts:

1. Start the tunnel (**`127.0.0.1:10005`** → Redshift).
2. Re-run **`python3 scripts/snapshot_redshift_to_duckdb.py`** (see root `README.md` — Path A) so DuckDB is rebuilt **from Redshift** at snapshot time.
3. Copy/rename to **`activationos_demo_2.duckdb`** as documented, refresh **`customer_mart.duckdb`** if needed, then run **`cube/scripts/seed_warehouse_from_duckdb.py`** into **`warehouse-postgres`** (`localhost:5433` from host).

**Alternative (no DuckDB middle):** **Meltano** Redshift → `warehouse-postgres` (`cube/README.md`, Path B) for continuous or incremental parity with prod.

**Summary:** DuckDB in this flow is an **optional staging format** for the seeder; **source of truth** for “fresh gold” is still **Redshift** when you run the snapshot (or Meltano).

---

## 3. Two delivery patterns (keep both)

### Pattern A — **Materialize in Redshift; CRM reads tables** (not Braze API)

- **Who owns Braze/CRM:** External CRM team; **not** necessarily wired through cdp-main APIs.
- **CDP / Reverse ETL role:** Run jobs that **write or refresh tables/views in Redshift** (e.g. `ext_braze.segment_*`, export marts, audience tables) that **CRM consumes with their own Redshift access**.
- **Scheduling / on-demand:** **Airflow** (or equivalent) runs **dbt**, **SQL COPY/INSERT**, or **Meltano** target-sink jobs on a schedule; same jobs can be **triggered manually** (Airflow UI “Trigger DAG”, CI, or a thin **cdp-main** endpoint that only enqueues Airflow if you add it later).
- **Today in repo:** Table **materialization to Redshift** is not the same code path as **segment → Braze REST** in `SyncEngine`; treat Pattern A as **orchestration + warehouse writes** (dbt under `platform/dbt`, Meltano, or custom SQL) **alongside** cdp-main for definitions and ops UX.

### Pattern B — **API push** (Braze / Attentive adapters)

- **cdp-main** **Sync** / **activation** flows read the audience (e.g. **Cube** / segment) and call **destination adapters** (`sync_engine`, Braze payload builders).
- **Scheduling / on-demand:** **`airflow/dags/activationos_sync_dag.py`** pattern — Airflow calls **`POST …/syncs/{id}/trigger`** (set `activationos_api_url` Airflow Variable to your API base, e.g. `http://localhost:8000/api/v1`).

Use **Pattern B** when the marketing platform is under your control and accepts API traffic; use **Pattern A** when downstream is **warehouse-first** (CRM SQL on Redshift).

---

## 4. Airflow: on-demand + scheduler

1. Set Airflow Variable **`activationos_api_url`** (see root `README.md` → Airflow Setup).
2. **Scheduled:** DAG schedule in `activationos_sync_dag.py` (or per-job DAGs) drives recurring syncs.
3. **On-demand:** Trigger DAG run from Airflow UI / CLI for the same DAG.

For **segment refresh → Redshift table** (Pattern A), add or reuse a DAG that runs **warehouse jobs** (dbt/Meltano/SQL), not necessarily the sync trigger DAG.

---

## 5. One-line mental model

```text
Redshift dev (tunnel :10005) ──► (snapshot | Meltano) ──► warehouse-postgres gold.*
       │
       ├──► Pattern A: jobs materialize tables IN Redshift → CRM reads Redshift
       └──► Pattern B: cdp-main sync/activation → Braze/Attentive API
              └── schedule / manual via Airflow → API trigger
```
