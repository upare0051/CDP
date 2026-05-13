-- Gold segment storage (dev / reference DDL)
-- Run against your Redshift dev instance as a superuser or schema owner.
-- Adjust DISTKEY/SORTKEY for your largest tables and join patterns.

CREATE SCHEMA IF NOT EXISTS gold;

-- 1) Segment metadata (one row per logical segment; updated on each successful refresh)
CREATE TABLE IF NOT EXISTS gold.segment_metadata (
    segment_id          BIGINT       NOT NULL,
    segment_title       VARCHAR(512) NOT NULL,
    segment_desc        VARCHAR(8192),
    created               TIMESTAMP    NOT NULL DEFAULT GETDATE(),
    updated               TIMESTAMP    NOT NULL DEFAULT GETDATE(),
    last_refreshed_dt     TIMESTAMP,
    PRIMARY KEY (segment_id)
)
DISTSTYLE KEY
DISTKEY (segment_id)
SORTKEY (segment_id);

COMMENT ON TABLE gold.segment_metadata IS 'Logical segment catalog mirrored from app; last_refreshed_dt advances on successful materialization.';

-- 2) Segment membership + payload (many rows per refresh run)
-- Minimal columns per product spec + run_id for refresh-over-time and overlap by version.
CREATE TABLE IF NOT EXISTS gold.segment_data (
    seg_id          BIGINT       NOT NULL,  -- same as segment_id (keeps your naming)
    cust_id         BIGINT       NOT NULL,
    json_payload    SUPER,                  -- use VARCHAR(65535) if SUPER unavailable
    run_id          VARCHAR(64)  NOT NULL,  -- e.g. UUID v4 per execution; enables history
    refreshed_at    TIMESTAMP    NOT NULL DEFAULT GETDATE(),
    PRIMARY KEY (seg_id, cust_id, run_id)
)
DISTSTYLE KEY
DISTKEY (cust_id)
COMPOUND SORTKEY (cust_id, seg_id, run_id);

COMMENT ON TABLE gold.segment_data IS 'Materialized segment membership per run_id; overlap analysis joins on cust_id across seg_id for fixed run_id or latest() per segment.';

-- Helpful for "latest run per segment" without window functions in every query
CREATE TABLE IF NOT EXISTS gold.segment_latest_run (
    seg_id      BIGINT       NOT NULL,
    run_id      VARCHAR(64)  NOT NULL,
    refreshed_at TIMESTAMP   NOT NULL,
    row_count   BIGINT,
    PRIMARY KEY (seg_id)
)
DISTSTYLE ALL;

COMMENT ON TABLE gold.segment_latest_run IS 'Pointer row updated atomically after each successful segment_data load for that seg_id.';
