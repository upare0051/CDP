select
    id as segment_id,
    name as segment_name,
    description as segment_description,
    filter_config,
    status as segment_status,
    estimated_count,
    last_count_at,
    ai_generated,
    ai_prompt,
    tags,
    created_at,
    updated_at,
    created_by
from {{ source('activationos', 'segments') }}
