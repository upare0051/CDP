select
    id as attribute_id,
    customer_id,
    lower(attribute_name) as attribute_name,
    nullif(trim(attribute_value), '') as attribute_value,
    lower(coalesce(attribute_type, 'string')) as attribute_type,
    source_connection_id,
    source_field,
    confidence_score,
    created_at,
    updated_at
from {{ source('bridgesync', 'customer_attributes') }}
