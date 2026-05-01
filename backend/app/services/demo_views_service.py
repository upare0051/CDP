"""Create and maintain demo-safe SQL views for Explorer."""

from sqlalchemy import text

from ..db import engine


DEMO_VIEW_DDL = [
    "CREATE SCHEMA IF NOT EXISTS activationos_transform",
    "DROP VIEW IF EXISTS demo_source_connections",
    """
    CREATE VIEW demo_source_connections AS
    SELECT
      id, name, source_type, is_active, last_tested_at, last_test_success, created_at, updated_at
    FROM source_connections
    """,
    "DROP VIEW IF EXISTS demo_destination_connections",
    """
    CREATE VIEW demo_destination_connections AS
    SELECT
      id, name, destination_type, rate_limit_per_second, batch_size,
      is_active, last_tested_at, last_test_success, created_at, updated_at
    FROM destination_connections
    """,
    "DROP VIEW IF EXISTS demo_sync_jobs",
    """
    CREATE VIEW demo_sync_jobs AS
    SELECT
      id, name, description, source_connection_id, source_schema, source_table,
      destination_connection_id, sync_mode, sync_key, schedule_type,
      is_active, is_paused, created_at, updated_at
    FROM sync_jobs
    """,
    "DROP VIEW IF EXISTS demo_field_mappings",
    """
    CREATE VIEW demo_field_mappings AS
    SELECT
      id, sync_job_id, source_field, source_field_type, destination_field,
      transformation, is_sync_key, is_required, created_at
    FROM field_mappings
    """,
    "DROP VIEW IF EXISTS demo_sync_runs",
    """
    CREATE VIEW demo_sync_runs AS
    SELECT
      id, sync_job_id, run_id, status, started_at, completed_at, duration_seconds,
      rows_read, rows_synced, rows_failed, rows_skipped, retry_count, created_at
    FROM sync_runs
    """,
    "DROP VIEW IF EXISTS demo_segments",
    """
    CREATE VIEW demo_segments AS
    SELECT
      id, name, description, filter_config, status, estimated_count, last_count_at,
      ai_generated, created_at, updated_at, tags
    FROM segments
    """,
    "DROP VIEW IF EXISTS demo_segment_memberships",
    """
    CREATE VIEW demo_segment_memberships AS
    SELECT id, segment_id, customer_id, computed_at
    FROM segment_memberships
    """,
    "DROP VIEW IF EXISTS demo_segment_activations",
    """
    CREATE VIEW demo_segment_activations AS
    SELECT
      id, segment_id, destination_id, name, frequency, status, field_mappings,
      last_sync_at, last_sync_count, total_synced, created_at, updated_at
    FROM segment_activations
    """,
    "DROP VIEW IF EXISTS demo_activation_runs",
    """
    CREATE VIEW demo_activation_runs AS
    SELECT
      id, run_id, activation_id, status, total_customers, synced_count, failed_count,
      skipped_count, started_at, completed_at, duration_seconds
    FROM activation_runs
    """,
    "DROP VIEW IF EXISTS demo_segment_exports",
    """
    CREATE VIEW demo_segment_exports AS
    SELECT
      id, segment_id, file_name, file_size, row_count, included_fields, created_at, expires_at
    FROM segment_exports
    """,
    "DROP VIEW IF EXISTS demo_writeback_jobs",
    """
    CREATE VIEW demo_writeback_jobs AS
    SELECT
      id, name, description, source_type, target_type, attribute_name,
      attribute_type, status, created_at, updated_at
    FROM writeback_jobs
    """,
    "DROP VIEW IF EXISTS demo_writeback_runs",
    """
    CREATE VIEW demo_writeback_runs AS
    SELECT
      id, job_id, run_type, status, total_candidates, total_updates, total_inserts,
      total_failed, started_at, completed_at, created_at
    FROM writeback_runs
    """,
    "DROP VIEW IF EXISTS demo_ai_customer_insights",
    """
    CREATE VIEW demo_ai_customer_insights AS
    WITH ltv AS (
      SELECT customer_id, CAST(NULLIF(attribute_value, '') AS REAL) AS lifetime_value
      FROM customer_attributes
      WHERE attribute_name = 'lifetime_value'
    ),
    orders AS (
      SELECT customer_id, CAST(NULLIF(attribute_value, '') AS REAL) AS total_orders
      FROM customer_attributes
      WHERE attribute_name = 'total_orders'
    ),
    tickets AS (
      SELECT customer_id, CAST(NULLIF(attribute_value, '') AS REAL) AS support_ticket_count
      FROM customer_attributes
      WHERE attribute_name = 'support_ticket_count'
    )
    SELECT
      p.id AS customer_id,
      p.external_id,
      'profile_analysis'::TEXT AS insight_kind,
      CASE
        WHEN (
          COALESCE(t.support_ticket_count, 0) * 0.1
          + CASE WHEN COALESCE(o.total_orders, 0) = 0 THEN 0.4 ELSE 0.0 END
        ) >= 0.3 THEN 'high'
        WHEN (
          COALESCE(t.support_ticket_count, 0) * 0.1
          + CASE WHEN COALESCE(o.total_orders, 0) = 0 THEN 0.4 ELSE 0.0 END
        ) >= 0.15 THEN 'medium'
        ELSE 'low'
      END AS churn_level,
      ROUND(
        CAST((
        CASE
          WHEN (
            COALESCE(t.support_ticket_count, 0) * 0.1
            + CASE WHEN COALESCE(o.total_orders, 0) = 0 THEN 0.4 ELSE 0.0 END
          ) > 1 THEN 1
          ELSE (
            COALESCE(t.support_ticket_count, 0) * 0.1
            + CASE WHEN COALESCE(o.total_orders, 0) = 0 THEN 0.4 ELSE 0.0 END
          )
        END
        ) AS NUMERIC)
      , 4) AS churn_score,
      ROUND(CAST(
        LEAST(
          1.0,
          GREATEST(
            0.0,
            (COALESCE(o.total_orders, 0) / 10.0)
            + (COALESCE(l.lifetime_value, 0) / 1000000.0)
            - (COALESCE(t.support_ticket_count, 0) / 20.0)
          )
        ) AS NUMERIC
      ), 4) AS engagement_score,
      CASE
        WHEN COALESCE(o.total_orders, 0) >= 8 THEN 'loyal'
        WHEN COALESCE(o.total_orders, 0) >= 4 THEN 'active'
        ELSE 'new_or_lapsing'
      END AS customer_segment,
      ROUND(CAST(COALESCE(l.lifetime_value, 0) AS NUMERIC), 2) AS lifetime_value,
      CONCAT(
        'Orders=', COALESCE(o.total_orders, 0),
        ', Tickets=', COALESCE(t.support_ticket_count, 0),
        ', LTV=', ROUND(CAST(COALESCE(l.lifetime_value, 0) AS NUMERIC), 2)
      ) AS summary,
      p.last_seen_at AS created_at
    FROM customer_profiles p
    LEFT JOIN ltv l ON l.customer_id = p.id
    LEFT JOIN orders o ON o.customer_id = p.id
    LEFT JOIN tickets t ON t.customer_id = p.id
    """,
    "DROP VIEW IF EXISTS activationos_transform.ai_customer_insights",
    """
    CREATE VIEW activationos_transform.ai_customer_insights AS
    SELECT
      customer_id,
      external_id,
      insight_kind,
      churn_level,
      churn_score,
      engagement_score,
      customer_segment,
      lifetime_value,
      summary,
      created_at
    FROM demo_ai_customer_insights
    """,
    "DROP VIEW IF EXISTS demo_ai_audience_recommendations",
    """
    CREATE VIEW demo_ai_audience_recommendations AS
    SELECT
      customer_id,
      external_id,
      CASE
        WHEN churn_score >= 0.3 THEN 'reduce_churn'
        WHEN lifetime_value >= 200000 THEN 'increase_revenue'
        ELSE 'improve_engagement'
      END AS goal,
      CASE
        WHEN churn_score >= 0.3 THEN 'high'
        WHEN churn_score >= 0.15 THEN 'medium'
        ELSE 'low'
      END AS priority,
      created_at
    FROM demo_ai_customer_insights
    """,
    "DROP VIEW IF EXISTS activationos_transform.ai_audience_recommendations",
    """
    CREATE VIEW activationos_transform.ai_audience_recommendations AS
    SELECT customer_id, external_id, goal, priority, created_at
    FROM demo_ai_audience_recommendations
    """,
]


def ensure_demo_views() -> None:
    """Create demo-safe SQL views for Explorer consumption."""
    for ddl in DEMO_VIEW_DDL:
        with engine.begin() as conn:
            conn.execute(text(ddl))
