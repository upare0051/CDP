select
    id as customer_id,
    external_id,
    email,
    phone,
    first_name,
    last_name,
    source_count,
    first_seen_at,
    last_seen_at,
    last_synced_at,
    created_at,
    updated_at
from {{ source('activationos', 'customer_profiles') }}
