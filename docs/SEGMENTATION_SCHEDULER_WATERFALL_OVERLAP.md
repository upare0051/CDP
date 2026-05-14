# Segmentation: scheduler, waterfall builder, overlap analysis

Engineering design aligned with ActivationOS (FastAPI + Postgres app DB, Redshift `gold`, Cube for warehouse-backed segments, Airflow for orchestration). Waterfall lives **inside** the existing segment builder (Braze-style), not a separate page.

---

## 1. Product / feature design

### 1.1 Schedule segments
- **User story:** Marketers define a segment once; it refreshes on a schedule or on demand; downstream activations always read a **named, versioned** snapshot in Redshift.
- **Cron:** Preset frequencies (hourly/daily/weekly) + optional “advanced” cron string (validated server-side).
- **On-demand:** “Refresh now” from segment detail / builder; shows queued → running → succeeded/failed with counts and duration.
- **Truth:** Redshift `ext_braze.segment_data` is the **system of record** for warehouse-scale membership; Postgres remains source for **definition** (JSON), **schedule**, and **run history**.

### 1.2 Waterfall (in segment builder)
- **User story:** Ordered **stages** (buckets). Each stage has inner rules with **AND/OR** (like Braze filter groups). A customer is assigned to the **first** stage whose rules match; later stages are skipped (**mutually exclusive** buckets within one waterfall segment).
- **Optional “remainder”** bucket: catch-all customers who matched none of the above (toggle).
- **UI:** Same page as today’s segment editor: toggle “Waterfall mode”, vertical ordered cards, drag reorder, per-stage AND/OR, optional estimated reach per stage (async or sampled).

### 1.3 Overlap analysis
- **User story:** Pick 2+ segments (by **logical id** and optionally **run_id** / “latest”), see intersection counts, % of each segment, and optional Venn-style summary (two-segment exact; 3+ as table + simple bar breakdown).
- **Filters:** As-of **run** (or latest), **as-of date** (use `updated_at` / snapshot date in metadata), optional attribute filter applied **after** membership resolve (second pass in SQL or pre-filter cohort table).

---

## 2. Technical architecture

**Opinionated simplest robust stack:**

| Concern | Choice |
|--------|--------|
| Orchestration | **Airflow** (already in repo): DAG `segment_refresh` with `PythonOperator` or ECS operator calling your worker |
| Trigger API | FastAPI: `POST /segments/{id}/refresh`, `PATCH /segments/{id}/schedule` |
| Execution | **Dedicated worker** (container or Celery): loads segment JSON → generates SQL or calls Cube Export API → `COPY` / `INSERT` into Redshift |
| Warehouse writes | **Append new `run_id` partition** in `ext_braze.segment_data`, then **swap pointer** in `ext_braze.segment_latest_run` in one transaction |
| Status | Postgres tables `segment_refresh_runs`, `segment_schedules` (queryable by UI) |
| Idempotency | `run_id` = deterministic hash(segment_id, definition_version, airflow_run_id) OR UUID per attempt |

**Why not only Redshift for scheduling?** Redshift doesn’t run cron; keep schedules in Postgres + Airflow is standard.

**Cube segments:** Worker uses existing `cube_query` → bulk extract `customer_id` + Braze identity fields (`external_id`, `email`, `phone`) + optional attributes → write Braze `payload`. **Legacy segments:** SQL against gold marts or staging (same worker interface).

---

## 3. Data model

### 3.1 Redshift (`ext_braze`) — your two tables + minimal addition

See `platform/redshift/sql/ext_braze_segment_storage_dev.sql`.

- **`ext_braze.segment_metadata`:** one row per `segment_id` (align with app `segments.id` as BIGINT). `last_refreshed_dt` updated when a run **succeeds**.
- **`ext_braze.segment_data`:** Braze-compatible columns **`external_id`**, **`payload`**, and **`updated_at`**; optional identity helpers **`email`** and **`phone`**; plus **`seg_id`**, **`run_id`**, and **`cust_id`** so refreshes don’t overwrite history and overlap can target a snapshot.
- **`ext_braze.segment_latest_run`:** optional pointer for O(1) “latest membership” without `MAX(run_id)` everywhere.

### 3.2 Postgres (app) — new / extended

- **`segment_schedules`:** `segment_id`, `enabled`, `cron`, `timezone`, `next_run_at`, `last_run_at`, `definition_version` (int, bump on save).
- **`segment_refresh_runs`:** `id`, `segment_id`, `run_id` (UUID, matches Redshift), `status` (queued|running|succeeded|failed), `started_at`, `finished_at`, `row_count`, `error`, `trigger` (schedule|manual|api).
- **`segments` extension:** `evaluation_mode` enum `flat | waterfall`, `waterfall_definition` JSON (nullable), `definition_version` int.

**Waterfall JSON (example):**

```json
{
  "version": 1,
  "remainder": true,
  "stages": [
    { "id": "s1", "label": "Lapsed", "group_logic": "AND", "filters": [ ... ] },
    { "id": "s2", "label": "VIP", "group_logic": "OR", "filters": [ ... ] }
  ]
}
```

Execution assigns `waterfall_stage` into `payload` for explainability.

---

## 4. API design

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/segments/{id}/refresh` | On-demand run; returns `run_id` |
| `GET` | `/api/v1/segments/{id}/refresh-runs` | List runs + statuses |
| `GET` | `/api/v1/segments/{id}/refresh-runs/{run_id}` | Detail + row_count |
| `PUT` | `/api/v1/segments/{id}/schedule` | Create/update cron + enable |
| `DELETE` | `/api/v1/segments/{id}/schedule` | Disable |
| `POST` | `/api/v1/segments/overlap` | Body: `{ segment_ids: [], run_mode: "latest"|"explicit", run_ids?: {} }` → counts + percentages |
| `GET` | `/api/v1/segments/{id}/preview` | Extend for waterfall per-stage estimates (optional async job) |

Authz: segment read/write as today; overlap = read on all selected segments.

---

## 5. UI / page design

- **Segment builder (existing):** Add toolbar toggles: **Flat** | **Waterfall**. Waterfall = ordered list of “stages” reusing current filter row components + stage-level AND/OR; drag handle; duplicate/delete stage; Braze-like “Search filter…” per stage.
- **Segment detail:** “Schedule” card (cron + timezone + next run), “Refresh now”, “Run history” table linking to Redshift run_id.
- **New route:** `/segments/overlap` — multi-select segments (chips), run mode (latest vs pick run from dropdown per segment), optional date filter, primary metric: pairwise matrix for 2 segments; for 3+ show table “intersection size” for selected set and Jaccard-like summary.

---

## 6. Implementation plan (practical order)

1. **Redshift DDL** in dev; `payload` must be VARCHAR/string and `updated_at` must be TIMESTAMPTZ for Braze CDI schema validation.
2. **Postgres migrations:** `segment_schedules`, `segment_refresh_runs`, `segments.evaluation_mode`, `waterfall_definition`, `definition_version`.
3. **Worker library:** `build_sql_from_flat_filter` / `build_sql_from_waterfall` / `cube_extract` → unified iterator of `(external_id, payload, updated_at)`.
4. **Redshift writer:** batched insert into `ext_braze.segment_data`; metadata upsert; pointer update.
5. **API:** refresh + schedule + list runs (stub worker first with dry-run).
6. **Airflow DAG** `segment_refresh` mirroring `activationos_sync_dag.py` pattern (Variable API URL, pull due segments, POST refresh).
7. **UI:** schedule + run history on segment detail; waterfall in `SegmentEditor.tsx` behind feature flag.
8. **Overlap API + page:** SQL for 2-segment intersection using `segment_latest_run` + join `segment_data` on `external_id` and matching `run_id` (or subquery latest per seg_id).

---

## 7. Risks and edge cases

| Risk | Mitigation |
|------|------------|
| Redshift load contention | Stagger Airflow pools; max concurrent refreshes per cluster |
| Huge segments | Chunked COPY; optional “sample overlap” mode |
| Definition change mid-run | `definition_version` in run row; reject completion if version advanced |
| Waterfall overlap between stages | Impossible by construction if engine assigns first match only |
| Flat vs waterfall confusion | Clear badge on segment list; migration path: one-way “convert to waterfall” copies filters into single stage |
| Overlap latest vs stale | Default “latest”; show `updated_at` in UI |
| Payload size limits | Keep `payload` lean enough for Redshift VARCHAR(65535); large blobs should use an S3 key reference in JSON if needed |

---

## 8. Suggested milestones

| Milestone | Deliverable |
|-----------|-------------|
| M0 | Redshift DDL + `segment_latest_run` documented |
| M1 | `segment_refresh_runs` + POST refresh (sync small segments only) |
| M2 | Redshift writer at scale + metadata + pointer |
| M3 | Airflow schedule + cron |
| M4 | Waterfall JSON schema + worker evaluation + builder UI |
| M5 | Overlap API + `/segments/overlap` page |
| M6 | Hardening: retries, alerts, cost caps, per-stage preview job |

---

## Assumptions (explicit)

- `cust_id` in Redshift aligns with **gold** customer key (same as Cube `customer_unified.customer_id` type); `external_id` defaults to that value when the source row does not provide a separate Braze external ID.
- Airflow (or similar) is available in prod; if not, use **AWS EventBridge + Lambda** or **Temporal** with the same API contracts.
- Overlap “at scale” assumes **DISTKEY(external_id)** and **compound sortkey** on `segment_data` as in the DDL file; add **VACUUM** / **ANALYZE** policy after bulk loads.
