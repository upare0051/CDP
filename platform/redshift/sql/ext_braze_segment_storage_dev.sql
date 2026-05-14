-- ext_braze segment storage (dev / reference DDL)
-- Run against your Redshift dev instance as a superuser or schema owner.
-- Adjust DISTKEY/SORTKEY for your largest tables and join patterns.

CREATE SCHEMA IF NOT EXISTS ext_braze;

-- 1) Segment metadata (one row per logical segment; updated on each successful refresh)
CREATE TABLE IF NOT EXISTS ext_braze.segment_metadata (
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

COMMENT ON TABLE ext_braze.segment_metadata IS 'Logical segment catalog mirrored from app; last_refreshed_dt advances on successful materialization.';

-- 2) Segment membership + payload (many rows per refresh run)
-- Braze-required columns: external_id (identity), payload, updated_at.
-- Keep seg_id/run_id/cust_id for segment scoping, run history, and analysis.
CREATE TABLE IF NOT EXISTS ext_braze.segment_data (
    seg_id          BIGINT        NOT NULL,  -- same as segment_id (keeps your naming)
    external_id     VARCHAR(256)  NOT NULL,  -- Braze identity column
    email           VARCHAR(512),            -- optional Braze identity column
    phone           VARCHAR(64),             -- optional Braze identity column
    payload         VARCHAR(65535),          -- Braze requires string/VARCHAR, not SUPER
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id          VARCHAR(64)   NOT NULL,  -- e.g. UUID v4 per execution; enables history
    cust_id         BIGINT,                  -- internal warehouse customer key
    PRIMARY KEY (seg_id, external_id, run_id)
)
DISTSTYLE KEY
DISTKEY (external_id)
COMPOUND SORTKEY (seg_id, run_id, updated_at);

COMMENT ON TABLE ext_braze.segment_data IS 'Braze-compatible materialized segment membership per run_id; query external_id, payload, updated_at for Braze CDI.';

-- Braze CDI query shape for a single segment's latest run:
-- SELECT external_id, payload, updated_at
-- FROM ext_braze.segment_data
-- WHERE seg_id = <segment_id>
--   AND run_id = (SELECT run_id FROM ext_braze.segment_latest_run WHERE seg_id = <segment_id>);

-- Helpful for "latest run per segment" without window functions in every query
CREATE TABLE IF NOT EXISTS ext_braze.segment_latest_run (
    seg_id      BIGINT       NOT NULL,
    run_id      VARCHAR(64)  NOT NULL,
    refreshed_at TIMESTAMP   NOT NULL,
    row_count   BIGINT,
    PRIMARY KEY (seg_id)
)
DISTSTYLE ALL;

COMMENT ON TABLE ext_braze.segment_latest_run IS 'Pointer row updated atomically after each successful segment_data load for that seg_id.';
