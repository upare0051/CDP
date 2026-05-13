# CDP segment → Dittofeed Manual segment mirror

## Why

The embedded Dittofeed journey builder's "Wait For" node reads its segment
options from `GET /api/segments/`. CDP segments live only in our Postgres
metadata DB (and Cube/Redshift materialization), so the dropdown was empty.
We mirror each *active* CDP segment as a Dittofeed **Manual** segment so it
shows up in the dropdown, then push membership separately.

## How

1. **Upsert**: `activate_segment` calls `dittofeed_client.upsert_manual_segment`
   (PUT `/api/segments/`) with a `Manual` entry node. The returned UUID is
   stored in `segments.dittofeed_segment_id` for subsequent updates.
2. **Delete**: `archive_segment` calls `delete_segment` (DELETE
   `/api/segments/`). The DELETE is body-based (not query-string), and 404
   is treated as already-gone.
3. **Membership push**: piggybacks on `sync_segment_to_redshift`. After a
   successful Redshift run, `_mirror_membership_to_dittofeed` collects
   `external_id` values from the same row set and posts them to
   `/api/segments/manual-segment/update` with `append=true`. This identifier
   matches what `DittofeedAdapter` uses as `userId` so the Wait For node can
   actually match users.
4. **Best-effort**: every Dittofeed call is wrapped in try/except. A
   Dittofeed outage logs a warning but never blocks the CDP-side
   activate/archive/sync.

## Schema

Added `segments.dittofeed_segment_id VARCHAR(64)` (nullable). The repo has
no Alembic, so the column is also added via an idempotent in-place
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in the FastAPI `lifespan`
startup hook (Postgres path) plus an `PRAGMA table_info`-gated `ALTER`
for the SQLite fallback.

## Identifier contract

Dittofeed `userId` must match what the rest of the activation pipeline
emits. The existing `DittofeedAdapter` sends Segment-style `identify`
events with `userId = sync_key value` (defaults to `external_id`). The
membership push uses `external_id` from the segment materialization rows
so the Wait For step advances the same users the destination adapter
identifies.

## Dittofeed lite caveat

The current `dittofeed-lite:v0.24.0-alpha.17` image does not start a
`compute-properties-queue-workflow` for our workspace by default. As a
result, `POST /api/segments/manual-segment/update` succeeds asynchronously
but the underlying workflow throws
`WorkflowNotFoundError: sql: no rows in result set` and membership never
materializes. The segment **does** appear in the journey builder dropdown
(upsert is unaffected), but Wait For will not match users until that
workflow is running. Out of scope for this change.

## Verified

- `python -m pytest tests/test_dittofeed_client.py` — 10/10 pass, covers
  upsert/delete/membership shapes and the 404 swallow.
- Live stack: `POST /api/v1/segments/{id}/activate` → segment appears in
  `GET /api/segments/?workspaceId=...` as `type=Manual`; `archive` removes
  it. Confirmed with the user's existing `Test Segment` (CDP id 1).
