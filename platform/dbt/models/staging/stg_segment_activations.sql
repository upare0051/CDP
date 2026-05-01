select
    id as activation_id,
    segment_id,
    destination_id,
    name as activation_name,
    frequency as activation_frequency,
    status as activation_status,
    field_mappings,
    last_sync_at,
    last_sync_count,
    total_synced,
    created_at,
    updated_at
from {{ source('bridgesync', 'segment_activations') }}
