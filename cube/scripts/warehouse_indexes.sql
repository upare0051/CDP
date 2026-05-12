-- Indexes on gold.customer_unified_attr for audience filter columns.
-- Run via: docker exec -i cdp-main-warehouse-postgres-1 psql -U cdp -d cdp_warehouse < cube/scripts/warehouse_indexes.sql
--
-- All built with CONCURRENTLY where possible so this is safe to re-run
-- against a hot warehouse. (Indexes are CREATE IF NOT EXISTS via
-- transactionless DDL.)

\timing on

-- Customer ID: makes joins and customer_id-lookup audiences fast.
CREATE INDEX IF NOT EXISTS idx_cua_customer_id
  ON gold.customer_unified_attr (customer_id);

-- Top-revenue / VIP audiences. DESC matches the ORDER BY direction.
CREATE INDEX IF NOT EXISTS idx_cua_revenue_52w_desc
  ON gold.customer_unified_attr (revenue_last_52_weeks DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_cua_total_revenue_l3y_desc
  ON gold.customer_unified_attr (total_revenue_l3y DESC NULLS LAST);

-- Lapsed-buyer / recency audiences.
CREATE INDEX IF NOT EXISTS idx_cua_days_since_last_order
  ON gold.customer_unified_attr (days_since_last_order);

CREATE INDEX IF NOT EXISTS idx_cua_last_order_date
  ON gold.customer_unified_attr (last_order_date DESC NULLS LAST);

-- Loyalty audiences.
CREATE INDEX IF NOT EXISTS idx_cua_loyalty_tier
  ON gold.customer_unified_attr (loyalty_tier_name)
  WHERE loyalty_tier_name IS NOT NULL;

-- Geo audiences.
CREATE INDEX IF NOT EXISTS idx_cua_digital_geo_segment
  ON gold.customer_unified_attr (digital_geo_segment);

CREATE INDEX IF NOT EXISTS idx_cua_state
  ON gold.customer_unified_attr (state);

-- Email reachability (partial: only the rows we want as filter target).
-- The filter "subscribed AND not bounced AND not suppressed" is a hot
-- audience path; a partial index keeps this tiny and selective.
CREATE INDEX IF NOT EXISTS idx_cua_email_reachable
  ON gold.customer_unified_attr (customer_id)
  WHERE email_subscribed = true
    AND email_hard_bounce = false
    AND email_suppressed = false;

CREATE INDEX IF NOT EXISTS idx_cua_sms_reachable
  ON gold.customer_unified_attr (customer_id)
  WHERE sms_subscribed = true;

-- Indexes on the underlying dim tables (used by customer_360 view joins).
CREATE INDEX IF NOT EXISTS idx_cd_customer_id
  ON gold.customer_dim (customer_id);
CREATE INDEX IF NOT EXISTS idx_cad_customer_id_current
  ON gold.customer_address_dim (customer_id) WHERE is_current = true;
CREATE INDEX IF NOT EXISTS idx_cid_customer_id_current
  ON gold.customer_identifier_dim (customer_id) WHERE is_current = true;
CREATE INDEX IF NOT EXISTS idx_cld_customer_id_current
  ON gold.customer_loyalty_dim (customer_id) WHERE is_current = true;
CREATE INDEX IF NOT EXISTS idx_ccpd_customer_id
  ON gold.customer_contact_prefs_dim (customer_id);
CREATE INDEX IF NOT EXISTS idx_cgs_customer_id
  ON gold.customer_geo_segment (customer_id);
CREATE INDEX IF NOT EXISTS idx_crf_customer_id
  ON gold.customer_rfm_fact (customer_id);
CREATE INDEX IF NOT EXISTS idx_olf_customer_id
  ON gold.order_line_fact (customer_id);

ANALYZE gold.customer_unified_attr;
ANALYZE gold.customer_dim;
ANALYZE gold.customer_address_dim;
ANALYZE gold.customer_identifier_dim;
ANALYZE gold.customer_loyalty_dim;
ANALYZE gold.customer_contact_prefs_dim;
ANALYZE gold.customer_geo_segment;
ANALYZE gold.customer_rfm_fact;
ANALYZE gold.order_line_fact;
