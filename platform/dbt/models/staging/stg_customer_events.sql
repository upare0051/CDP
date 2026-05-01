select
    id as event_id,
    customer_id,
    lower(event_type) as event_type,
    lower(coalesce(event_category, 'system')) as event_category,
    title,
    description,
    event_data,
    source_connection_id,
    destination_connection_id,
    sync_run_id,
    occurred_at
from {{ source('bridgesync', 'customer_events') }}
