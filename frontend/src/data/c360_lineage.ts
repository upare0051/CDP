export type UpstreamTable = { id: string; label: string; desc: string };
export type LineageEdge = { from: string; to: string };

// Ported from `c360-leadership-frontend/src/data/c360_reference.js`
export const UPSTREAM_TABLES: { bronze: UpstreamTable[]; silver: UpstreamTable[] } = {
  bronze: [
    { id: 'br_braze_email_bounce', label: 'br_braze_email_bounce', desc: 'Braze hard-bounce email list.' },
    { id: 'br_braze_email_soft_bounce', label: 'br_braze_email_soft_bounce', desc: 'Braze soft-bounce email list (subtracted from hard bounce).' },
    { id: 'br_holiday_calendar', label: 'br_holiday_calendar', desc: 'Calendar of promotional dates: Aloversary, Early Access, Singles Day, BFCM by fiscal_year.' },
  ],
  silver: [
    { id: 'sil_customer_dim', label: 'sil_customer_dim', desc: 'Silver customer profile — Shopify customer master with name, email, phone, birthday, loyalty, address.' },
    { id: 'sil_shopify_order_dim', label: 'sil_shopify_order_dim', desc: 'Silver order header — one row per order with processed_at, cancelled_at, destination_country_code, location_id.' },
    { id: 'sil_shopify_order_line_items_dim', label: 'sil_shopify_order_line_items_dim', desc: 'Silver order line items — one row per line with product, price, digital_vs_retail, cancelled_at.' },
    { id: 'sil_shopify_order_line_item_facts', label: 'sil_shopify_order_line_item_facts', desc: 'Silver order line facts — gross_sales_usd, total_discounts_usd, line_item_duties_usd, subtotal_refunded.' },
    { id: 'sil_braze_latest_user_status', label: 'sil_braze_latest_user_status', desc: 'Silver Braze — latest email subscription status per shopify_customer_id (platform=yoga, channel=email).' },
    { id: 'sil_attentive_sms_subscriber_status', label: 'sil_attentive_sms_subscriber_status', desc: 'Silver Attentive — latest SMS subscription status per subscriber_key (phone).' },
    { id: 'sil_airship_push_subscriber_status', label: 'sil_airship_push_subscriber_status', desc: 'Silver Airship — latest push subscription per named_user_id (email), per device channel.' },
    { id: 'sil_retail_locations', label: 'sil_retail_locations', desc: 'Silver retail locations — location_id to country mapping for geo segmentation.' },
  ],
};

export const LINEAGE_EDGES: LineageEdge[] = [
  // Bronze → Gold (direct refs)
  { from: 'br_braze_email_bounce', to: 'customer_contact_prefs_dim' },
  { from: 'br_braze_email_soft_bounce', to: 'customer_contact_prefs_dim' },
  { from: 'br_holiday_calendar', to: 'customer_unified_attr' },
  // Silver → Gold
  { from: 'sil_customer_dim', to: 'customer_dim' },
  { from: 'sil_customer_dim', to: 'customer_identifier_dim' },
  { from: 'sil_customer_dim', to: 'customer_address_dim' },
  { from: 'sil_customer_dim', to: 'customer_loyalty_dim' },
  { from: 'sil_customer_dim', to: 'customer_contact_prefs_dim' },
  { from: 'sil_shopify_order_dim', to: 'customer_rfm_fact' },
  { from: 'sil_shopify_order_dim', to: 'customer_geo_segment' },
  { from: 'sil_shopify_order_line_items_dim', to: 'order_line_fact' },
  { from: 'sil_shopify_order_line_items_dim', to: 'customer_geo_segment' },
  { from: 'sil_shopify_order_line_item_facts', to: 'order_line_fact' },
  { from: 'sil_braze_latest_user_status', to: 'customer_contact_prefs_dim' },
  { from: 'sil_attentive_sms_subscriber_status', to: 'customer_contact_prefs_dim' },
  { from: 'sil_airship_push_subscriber_status', to: 'customer_contact_prefs_dim' },
  { from: 'sil_retail_locations', to: 'customer_geo_segment' },
  // Gold → Gold (feeds into unified_attr)
  { from: 'customer_dim', to: 'customer_unified_attr' },
  { from: 'customer_identifier_dim', to: 'customer_unified_attr' },
  { from: 'customer_address_dim', to: 'customer_unified_attr' },
  { from: 'customer_loyalty_dim', to: 'customer_unified_attr' },
  { from: 'customer_contact_prefs_dim', to: 'customer_unified_attr' },
  { from: 'customer_geo_segment', to: 'customer_unified_attr' },
  { from: 'customer_rfm_fact', to: 'customer_unified_attr' },
  { from: 'order_line_fact', to: 'customer_rfm_fact' },
  { from: 'order_line_fact', to: 'customer_unified_attr' },
];

