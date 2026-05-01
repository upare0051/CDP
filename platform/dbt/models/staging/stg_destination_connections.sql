select
    id as destination_id,
    name as destination_name,
    destination_type,
    api_endpoint,
    braze_app_id,
    attentive_api_url,
    is_active,
    created_at,
    updated_at
from {{ source('bridgesync', 'destination_connections') }}
