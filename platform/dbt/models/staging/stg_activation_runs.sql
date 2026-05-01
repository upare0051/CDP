select
    id as activation_run_pk,
    run_id as activation_run_id,
    activation_id,
    status as run_status,
    total_customers,
    synced_count,
    failed_count,
    skipped_count,
    started_at,
    completed_at,
    duration_seconds,
    error_message,
    error_details
from {{ source('activationos', 'activation_runs') }}
