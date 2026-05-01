select
    id as segment_membership_id,
    segment_id,
    customer_id,
    computed_at
from {{ source('bridgesync', 'segment_memberships') }}
