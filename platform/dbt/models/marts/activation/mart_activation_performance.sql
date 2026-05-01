with activations as (
    select * from {{ ref('stg_segment_activations') }}
),

runs as (
    select * from {{ ref('stg_activation_runs') }}
),

destinations as (
    select * from {{ ref('stg_destination_connections') }}
),

run_agg as (
    select
        activation_id,
        count(*) as total_runs,
        count(case when run_status = 'completed' then 1 end) as completed_runs,
        count(case when run_status = 'failed' then 1 end) as failed_runs,
        sum(coalesce(total_customers, 0)) as total_customers_processed,
        sum(coalesce(synced_count, 0)) as total_synced_count,
        sum(coalesce(failed_count, 0)) as total_failed_count,
        max(started_at) as last_run_started_at,
        max(completed_at) as last_run_completed_at
    from runs
    group by activation_id
)

select
    a.activation_id,
    a.segment_id,
    a.destination_id,
    d.destination_name,
    d.destination_type,
    a.activation_name,
    a.activation_frequency,
    a.activation_status,
    a.last_sync_at,
    a.last_sync_count,
    a.total_synced,
    a.created_at,
    a.updated_at,

    coalesce(r.total_runs, 0) as total_runs,
    coalesce(r.completed_runs, 0) as completed_runs,
    coalesce(r.failed_runs, 0) as failed_runs,
    coalesce(r.total_customers_processed, 0) as total_customers_processed,
    coalesce(r.total_synced_count, 0) as total_synced_count,
    coalesce(r.total_failed_count, 0) as total_failed_count,
    r.last_run_started_at,
    r.last_run_completed_at
from activations a
left join run_agg r on a.activation_id = r.activation_id
left join destinations d on a.destination_id = d.destination_id
