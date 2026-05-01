/**
 * C360 Data Model Reference — DBT docs (schema.yml + docs/*.md)
 *
 * Source: `alo-data-stack/is-redshift/warehouse/{models,snapshots}/c360`
 *
 * This file is intentionally static so `/reference` renders even when Redshift is unavailable;
 * the page will still overlay live Redshift column types when available.
 */

// NOTE: This file is intentionally "JS-style" but typed loosely for speed.
// The Reference page consumes it as read-only metadata.

export const MODEL_CATEGORIES = [
  { id: 'customer-profile', label: 'Customer Profile', icon: '👤', description: 'Core customer identity, address, and identifier tables' },
  { id: 'customer-attributes', label: 'Customer Attributes', icon: '🧩', description: 'Unified attributes, contact preferences, and geo segments' },
  { id: 'transactions', label: 'Transactions', icon: '🛒', description: 'Order line-level fact table with revenue, quantity, and channel' },
  { id: 'rfm-behavior', label: 'RFM & Behavior', icon: '📈', description: 'Recency, frequency, monetary metrics across L52W and L3Y windows' },
  { id: 'loyalty', label: 'Loyalty', icon: '⭐', description: 'Loyalty enrollment, tier, and membership history (SCD2)' },
];

export const GLOSSARY = [
  { term: 'L52W', definition: 'Last 52 weeks — trailing 364 days from current_date (not calendar weeks).' },
  { term: 'L3Y', definition: 'Last 3 years — trailing 1,095 days from current_date.' },
  { term: 'SCD Type 1', definition: 'Slowly Changing Dimension Type 1 — overwrites old values in place; no version history.' },
  { term: 'SCD Type 2', definition: 'Slowly Changing Dimension Type 2 — maintains version history with effective_from / effective_to timestamps. Current row has effective_to = 9999-12-31.' },
  { term: 'RFM', definition: 'Recency, Frequency, Monetary — customer scoring framework based on order behavior.' },
  { term: 'digital_vs_retail', definition: 'Line-level channel classification. L52W/L3Y/participation metrics only count digital and retail lines (excludes other channel types).' },
  { term: 'line_revenue', definition: 'Net line revenue = gross_sales_usd − total_discounts_usd − line_item_duties_usd.' },
  { term: 'DA', definition: 'Data Activation — downstream consumer of C360 models.' },
  { term: 'Aloversary', definition: 'Annual promotional event; participation tracked per fiscal year via br_holiday_calendar (Aloversary FY 2025 were held from 2025-04-26 to 2025-05-02. FY 2026 will be held from 2026-05-02 to 2026-05-08).' },
  { term: 'Holiday sale window', definition: 'Early Access + Singles Day + BFCM promotional dates (excludes Aloversary).' },
  { term: 'customer_id', definition: 'Shopify customer id (BIGINT) — primary business key across all C360 models.' },
  { term: 'Fiscal Year (FY)', definition: 'Company fiscal year. Participation flags are named by FY (e.g. participated_fy2025_aloversary).' },
];

export type ReferenceColumn = {
  name: string;
  type?: string;
  description?: string;
  pk?: boolean;
};

export type ReferenceModel = {
  id: string;
  name: string;
  category: string;
  scdType: 'SCD1' | 'SCD2' | 'Table';
  grain: string;
  overview: string;
  sources: string[];
  columns: ReferenceColumn[];
  sampleSql: string;
};

export const MODELS = [
  {
    id: 'customer_dim',
    name: 'customer_dim',
    category: 'customer-profile',
    scdType: 'SCD1',
    grain: 'One row per customer_id.',
    overview:
      'SCD Type 1 customer profile: first name, last name, birthdate per customer_id from sil_customer_dim. Address history: customer_address_dim. Loyalty: customer_loyalty_dim. Geo: customer_geo_segment.',
    sources: ['sil_customer_dim'],
    columns: [
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id (business key).', pk: true },
      { name: 'first_name', type: 'VARCHAR', description: 'First name from Shopify profile.' },
      { name: 'last_name', type: 'VARCHAR', description: 'Last name from Shopify profile.' },
      { name: 'birthdate', type: 'DATE', description: 'Birth date when present (from loyalty-enriched silver).' },
      { name: 'etl_loaded_at', type: 'TIMESTAMP', description: 'Row build timestamp.' },
    ],
    sampleSql: `SELECT customer_id, first_name, last_name, birthdate\nFROM gold.customer_dim\nLIMIT 10;`,
  },
  {
    id: 'customer_address_dim',
    name: 'customer_address_dim',
    category: 'customer-profile',
    scdType: 'SCD2',
    grain: "One row per (customer_id, version). Current row: effective_to = cast('9999-12-31' as timestamp).",
    overview:
      'Default address attributes per customer_id with SCD Type 2 history. Implemented as a dbt snapshot on sil_customer_dim (country_code, province/state, city, zip).',
    sources: ['sil_customer_dim (snapshot: customer_address_dim)'],
    columns: [
      { name: 'address_sk', type: 'VARCHAR', description: 'SCD2 row id (dbt_scd_id).', pk: true },
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id (business key).' },
      { name: 'country_code', type: 'VARCHAR', description: 'Customer country code.' },
      { name: 'state', type: 'VARCHAR', description: 'Province / state.' },
      { name: 'city', type: 'VARCHAR', description: 'City.' },
      { name: 'zip_code', type: 'VARCHAR', description: 'Postal code.' },
      { name: 'effective_from', type: 'TIMESTAMP', description: 'Row version effective start (SCD2).' },
      { name: 'effective_to', type: 'TIMESTAMP', description: 'Row version effective end; open-ended uses sentinel date.' },
      { name: 'snapshot_updated_at', type: 'TIMESTAMP', description: 'Last snapshot run time for this row version.' },
    ],
    sampleSql: `SELECT customer_id, country_code, state, city, zip_code, effective_from, effective_to\nFROM gold.customer_address_dim\nWHERE effective_to = cast('9999-12-31' as timestamp)\nLIMIT 10;`,
  },
  {
    id: 'customer_identifier_dim',
    name: 'customer_identifier_dim',
    category: 'customer-profile',
    scdType: 'SCD2',
    grain: "One row per (customer_id, version). Current row: effective_to = cast('9999-12-31' as timestamp).",
    overview:
      'Current and historical email, phone, and platform attributes per Shopify customer_id. SCD Type 2 via dbt snapshot check on email, phone, source_system; includes email_norm and phone_norm for joins.',
    sources: ['sil_customer_dim (snapshot: customer_identifier_dim)'],
    columns: [
      { name: 'contact_sk', type: 'VARCHAR', description: 'Row version id (dbt_scd_id).', pk: true },
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id.' },
      { name: 'email', type: 'VARCHAR', description: 'Raw email from source.' },
      { name: 'email_norm', type: 'VARCHAR', description: 'Lowercased, trimmed email for joins.' },
      { name: 'phone', type: 'VARCHAR', description: 'Raw phone from source.' },
      { name: 'phone_norm', type: 'VARCHAR', description: 'Digits-only phone for joins (SMS).' },
      { name: 'source_system', type: 'VARCHAR', description: 'Platform / source system from sil_customer_dim.platform.' },
      { name: 'effective_from', type: 'TIMESTAMP', description: 'Row version effective start (SCD2).' },
      { name: 'effective_to', type: 'TIMESTAMP', description: 'Row version effective end; open-ended uses sentinel date.' },
      { name: 'snapshot_updated_at', type: 'TIMESTAMP', description: 'Last snapshot run time for this row version.' },
    ],
    sampleSql: `SELECT customer_id, email, phone, source_system, effective_from, effective_to\nFROM gold.customer_identifier_dim\nWHERE effective_to = cast('9999-12-31' as timestamp)\nLIMIT 10;`,
  },
  {
    id: 'customer_loyalty_dim',
    name: 'customer_loyalty_dim',
    category: 'loyalty',
    scdType: 'SCD2',
    grain: "One row per (customer_id, version). Current row: effective_to = cast('9999-12-31' as timestamp).",
    overview:
      'Loyalty enrollment, tier, and membership window per customer_id with SCD Type 2 via dbt snapshot on enrollment and loyalty columns from sil_customer_dim.',
    sources: ['sil_customer_dim (snapshot: customer_loyalty_dim)'],
    columns: [
      { name: 'loyalty_sk', type: 'VARCHAR', description: 'Row version id (dbt_scd_id).', pk: true },
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id (business key).' },
      { name: 'has_loyalty_account', type: 'BOOLEAN', description: 'True when loyalty enrollment flag is true in source.' },
      { name: 'loyalty_enrolled', type: 'BOOLEAN', description: 'Same as has_loyalty_account (DA-facing alias).' },
      { name: 'loyalty_id', type: 'VARCHAR', description: 'Loyalty program customer id (string).' },
      { name: 'loyalty_tier_name', type: 'VARCHAR', description: 'Current tier name from source.' },
      { name: 'membership_started_at', type: 'TIMESTAMP', description: 'Loyalty membership start timestamp.' },
      { name: 'membership_expires_at', type: 'DATE', description: 'Membership end date when applicable.' },
      { name: 'effective_from', type: 'TIMESTAMP', description: 'Row version effective start (SCD2).' },
      { name: 'effective_to', type: 'TIMESTAMP', description: 'Row version effective end.' },
      { name: 'snapshot_updated_at', type: 'TIMESTAMP', description: 'Last snapshot run time for this row version.' },
    ],
    sampleSql: `SELECT customer_id, loyalty_enrolled, loyalty_tier_name, membership_started_at, membership_expires_at\nFROM gold.customer_loyalty_dim\nWHERE effective_to = cast('9999-12-31' as timestamp)\nLIMIT 10;`,
  },
  {
    id: 'customer_contact_prefs_dim',
    name: 'customer_contact_prefs_dim',
    category: 'customer-attributes',
    scdType: 'SCD1',
    grain: 'One row per customer_id.',
    overview:
      'Email, SMS, and push subscription state and metadata per customer_id. Built from Braze latest email, bounce lists, Attentive (SMS), and Airship (push). SCD Type 1 incremental by customer_id.',
    sources: [
      'sil_customer_dim',
      'sil_braze_latest_user_status',
      'br_braze_email_bounce / br_braze_email_soft_bounce',
      'sil_attentive_sms_subscriber_status',
      'sil_airship_push_subscriber_status',
    ],
    columns: [
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id (PK).', pk: true },
      { name: 'email_subscribed', type: 'BOOLEAN', description: 'True only when latest Braze status is opted_in.' },
      { name: 'braze_subscription_status', type: 'VARCHAR', description: 'Braze email channel status (opted_in, subscribed, unsubscribed, hardbounce, other).' },
      { name: 'email_last_status_changed_at', type: 'TIMESTAMP', description: 'Latest Braze state change time used.' },
      { name: 'email_source', type: 'VARCHAR', description: 'e.g. braze.' },
      { name: 'email_hard_bounce', type: 'BOOLEAN', description: 'True if email in hard bounce minus soft bounce.' },
      { name: 'email_suppressed', type: 'BOOLEAN', description: 'Reserved / placeholder.' },
      { name: 'sms_subscribed', type: 'BOOLEAN', description: 'True when Attentive status is subscribed.' },
      { name: 'sms_status', type: 'VARCHAR', description: 'Latest SMS status.' },
      { name: 'sms_last_status_changed_at', type: 'TIMESTAMP', description: 'Last SMS status change.' },
      { name: 'sms_source', type: 'VARCHAR', description: 'e.g. attentive.' },
      { name: 'push_enabled', type: 'BOOLEAN', description: 'True if any device has subscribed status (user-level max).' },
      { name: 'push_status', type: 'VARCHAR', description: 'Aggregated push status.' },
      { name: 'push_last_status_changed_at', type: 'TIMESTAMP', description: 'Latest push activity.' },
      { name: 'push_source', type: 'VARCHAR', description: 'e.g. airship.' },
      { name: 'push_devices_count', type: 'INTEGER', description: 'Distinct channel count for user.' },
      { name: 'preferred_comm_channel', type: 'VARCHAR', description: 'email / sms / push / none from priority rules.' },
      { name: 'total_channels_subscribed', type: 'INTEGER', description: 'Sum of subscribed channels.' },
      { name: 'email_last_subscription_date', type: 'TIMESTAMP', description: 'Last Braze change when subscribed.' },
      { name: 'email_last_unsubscribe_date', type: 'TIMESTAMP', description: 'Last Braze change when not subscribed.' },
      { name: 'sms_last_subscription_date', type: 'TIMESTAMP', description: 'Last SMS change when subscribed.' },
      { name: 'sms_last_unsubscribe_date', type: 'TIMESTAMP', description: 'Last SMS change when not subscribed.' },
      { name: 'push_last_subscription_date', type: 'TIMESTAMP', description: 'Last push activity when enabled.' },
      { name: 'created_at', type: 'TIMESTAMP', description: 'Row build time.' },
      { name: 'updated_at', type: 'TIMESTAMP', description: 'Row build time.' },
    ],
    sampleSql: `SELECT customer_id, email_subscribed, sms_subscribed, push_enabled, preferred_comm_channel\nFROM gold.customer_contact_prefs_dim\nLIMIT 10;`,
  },
  {
    id: 'customer_geo_segment',
    name: 'customer_geo_segment',
    category: 'customer-attributes',
    scdType: 'Table',
    grain: 'One row per customer_id.',
    overview:
      'Domestic / International / Both / Unknown segments from order history: digital uses destination_country_code; omni includes retail using sil_retail_locations.country. Full table rebuild each run.',
    sources: ['sil_shopify_order_line_items_dim', 'sil_shopify_order_dim', 'sil_retail_locations'],
    columns: [
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id.', pk: true },
      { name: 'digital_geo_segment', type: 'VARCHAR', description: 'Segment from digital orders only: Domestic, International, Both, Unknown.' },
      { name: 'omni_geo_segment', type: 'VARCHAR', description: 'Segment across digital + retail channels.' },
      { name: 'domestic_international_customer', type: 'VARCHAR', description: 'Rollup from omni segment: Domestic, International, Both, Unknown.' },
      { name: 'etl_loaded_at', type: 'TIMESTAMP', description: 'Build timestamp for this row.' },
    ],
    sampleSql: `SELECT customer_id, digital_geo_segment, omni_geo_segment, domestic_international_customer\nFROM gold.customer_geo_segment\nLIMIT 10;`,
  },
  {
    id: 'order_line_fact',
    name: 'order_line_fact',
    category: 'transactions',
    scdType: 'Table',
    grain: 'One row per order_line_id.',
    overview:
      'Order line grain: one row per Shopify line item. Line revenue = gross_sales_usd - total_discounts_usd - line_item_duties_usd. Excludes cancelled orders.',
    sources: ['sil_shopify_order_line_items_dim', 'sil_shopify_order_line_item_facts'],
    columns: [
      { name: 'order_line_id', type: 'VARCHAR', description: 'Shopify line item id (string).', pk: true },
      { name: 'order_id', type: 'VARCHAR', description: 'Parent order id.' },
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id.' },
      { name: 'order_processed_date', type: 'DATE', description: 'Order processed date (UTC date from silver order dim).' },
      { name: 'order_processed_date_pst', type: 'DATE', description: 'Order processed date in US/Pacific.' },
      { name: 'order_processed_at_pst', type: 'TIMESTAMP', description: 'Order processed timestamp in US/Pacific.' },
      { name: 'product_variant_key', type: 'VARCHAR', description: 'Concatenation product_id:variant_id for joins to product catalog.' },
      { name: 'product_id', type: 'VARCHAR', description: 'Shopify product id.' },
      { name: 'variant_id', type: 'VARCHAR', description: 'Shopify variant id.' },
      { name: 'qty', type: 'DECIMAL', description: 'Units ordered from line facts.' },
      { name: 'unit_price', type: 'DECIMAL', description: 'Unit price from line dimension.' },
      { name: 'line_revenue', type: 'DECIMAL', description: 'gross_sales_usd - total_discounts_usd - line_item_duties_usd.' },
      { name: 'discount_amount', type: 'DECIMAL', description: 'total_discounts_usd from facts.' },
      { name: 'refund_amount', type: 'DECIMAL', description: 'subtotal_refunded from facts.' },
      { name: 'digital_vs_retail', type: 'VARCHAR', description: 'Channel classification on the line (e.g. digital vs retail).' },
      { name: 'etl_loaded_at', type: 'TIMESTAMP', description: 'Row load timestamp.' },
    ],
    sampleSql: `SELECT order_line_id, order_id, customer_id, line_revenue, digital_vs_retail\nFROM gold.order_line_fact\nLIMIT 10;`,
  },
  {
    id: 'customer_rfm_fact',
    name: 'customer_rfm_fact',
    category: 'rfm-behavior',
    scdType: 'Table',
    grain: 'One row per customer_id.',
    overview:
      'RFM fact per customer: all-time first/last order dates, days-since, trailing 364-day (L52W) order count and revenue, and trailing 1,095-day (3-year) aggregates and avg days between orders.',
    sources: ['sil_shopify_order_dim', 'order_line_fact'],
    columns: [
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id.', pk: true },
      { name: 'as_of_date', type: 'DATE', description: 'Snapshot date (current_date at build).' },
      { name: 'first_order_date', type: 'DATE', description: 'All-time first order date.' },
      { name: 'last_order_date', type: 'DATE', description: 'All-time last order date.' },
      { name: 'days_since_first_order', type: 'INTEGER', description: 'Days from first_order_date to current_date.' },
      { name: 'days_since_last_order', type: 'INTEGER', description: 'Days from last_order_date to current_date.' },
      { name: 'orders_last_52_weeks', type: 'BIGINT', description: 'Distinct order count in trailing 364 days (digital/retail lines only).' },
      { name: 'revenue_last_52_weeks', type: 'DECIMAL', description: 'Sum of line_revenue in trailing 364 days (digital/retail lines only).' },
      { name: 'rfm_3yr_as_of_date', type: 'DATE', description: 'As-of date for 3-year window metrics.' },
      { name: 'total_orders_l3y', type: 'BIGINT', description: 'Distinct orders in trailing 1,095 days.' },
      { name: 'total_revenue_l3y', type: 'DECIMAL', description: 'Sum of line_revenue in trailing 1,095 days.' },
      { name: 'total_units_l3y', type: 'DECIMAL', description: 'Sum of qty in trailing 1,095 days.' },
      { name: 'revenue_per_unit_l3y', type: 'DECIMAL', description: 'total_revenue_l3y / total_units_l3y; 0 when no units.' },
      { name: 'avg_days_between_orders_l3y', type: 'DECIMAL', description: 'Average gap between consecutive orders in trailing 1,095 days.' },
      { name: 'etl_loaded_at', type: 'TIMESTAMP', description: 'Row load timestamp.' },
    ],
    sampleSql: `SELECT customer_id, orders_last_52_weeks, revenue_last_52_weeks, total_orders_l3y, total_revenue_l3y\nFROM gold.customer_rfm_fact\nLIMIT 10;`,
  },
  {
    id: 'customer_unified_attr',
    name: 'customer_unified_attr',
    category: 'customer-attributes',
    scdType: 'Table',
    grain: 'One row per customer_id.',
    overview:
      'Single DA-facing table assembled from customer_dim (population) with left joins to current SCD2 loyalty and identifiers, contact prefs, geo segments, RFM, and fiscal-year holiday participation derived from order_line_fact joined to br_holiday_calendar.',
    sources: [
      'customer_dim',
      'customer_identifier_dim (current)',
      'customer_loyalty_dim (current)',
      'customer_contact_prefs_dim',
      'customer_geo_segment',
      'customer_rfm_fact',
      'order_line_fact + br_holiday_calendar',
    ],
    columns: [
      { name: 'customer_id', type: 'BIGINT', description: 'Shopify customer id (one row per customer in customer_dim).', pk: true },
      { name: 'email', type: 'VARCHAR', description: 'Raw email from current customer_identifier_dim row (SCD2 current version).' },
      { name: 'phone', type: 'VARCHAR', description: 'Raw phone from current customer_identifier_dim row (SCD2 current version).' },
      { name: 'loyalty_enrolled', type: 'BOOLEAN', description: 'Same as has_loyalty_account from loyalty dim.' },
      { name: 'loyalty_tier_name', type: 'VARCHAR', description: 'Current tier.' },
      { name: 'membership_started_at', type: 'TIMESTAMP', description: 'Loyalty membership start.' },
      { name: 'membership_expires_at', type: 'DATE', description: 'Loyalty membership end date.' },
      { name: 'digital_geo_segment', type: 'VARCHAR', description: 'Digital-only geo segment.' },
      { name: 'omni_geo_segment', type: 'VARCHAR', description: 'Omni-channel geo segment.' },
      { name: 'domestic_international_customer', type: 'VARCHAR', description: 'Rollup from omni_geo_segment.' },
      { name: 'email_subscribed', type: 'BOOLEAN', description: 'True when opted in to email.' },
      { name: 'sms_subscribed', type: 'BOOLEAN', description: 'True when SMS subscribed.' },
      { name: 'push_enabled', type: 'BOOLEAN', description: 'True when push is active.' },
      { name: 'preferred_comm_channel', type: 'VARCHAR', description: 'Derived preferred channel (email / sms / push / none).' },
      { name: 'first_order_date', type: 'DATE', description: 'All-time first order.' },
      { name: 'last_order_date', type: 'DATE', description: 'All-time last order.' },
      { name: 'orders_last_52_weeks', type: 'BIGINT', description: 'L52W order count.' },
      { name: 'revenue_last_52_weeks', type: 'DECIMAL', description: 'L52W revenue.' },
      { name: 'total_orders_l3y', type: 'BIGINT', description: 'Orders in last 1,095 days.' },
      { name: 'total_revenue_l3y', type: 'DECIMAL', description: 'Revenue in last 1,095 days.' },
      { name: 'avg_days_between_orders_l3y', type: 'DECIMAL', description: 'Average days between orders over 1,095 days.' },
      { name: 'participated_fy2023_aloversary', type: 'INTEGER', description: '1 if any qualifying digital/retail line on Aloversary FY2023 date; else 0.' },
      { name: 'participated_fy2024_aloversary', type: 'INTEGER', description: 'Same for FY2024.' },
      { name: 'participated_fy2025_aloversary', type: 'INTEGER', description: 'Same for FY2025.' },
      { name: 'participated_fy2026_aloversary', type: 'INTEGER', description: 'Same for FY2026.' },
      { name: 'participated_fy2023_holiday', type: 'INTEGER', description: '1 if any qualifying line on Early Access/Singles Day/BFCM FY2023 date; else 0.' },
      { name: 'participated_fy2024_holiday', type: 'INTEGER', description: 'Same for FY2024.' },
      { name: 'participated_fy2025_holiday', type: 'INTEGER', description: 'Same for FY2025.' },
      { name: 'participated_fy2026_holiday', type: 'INTEGER', description: 'Same for FY2026.' },
    ],
    sampleSql: `SELECT *\nFROM gold.customer_unified_attr\nLIMIT 10;`,
  },
 ] as ReferenceModel[];

export { LINEAGE_EDGES, UPSTREAM_TABLES } from '@/data/c360_lineage';


