with segments as (
    select * from {{ ref('stg_segments') }}
),

memberships as (
    select * from {{ ref('stg_segment_memberships') }}
),

customer_360 as (
    select * from {{ ref('mart_customer_360') }}
),

segment_counts as (
    select
        segment_id,
        count(*) as computed_member_count,
        max(computed_at) as last_membership_compute_at
    from memberships
    group by segment_id
),

segment_value as (
    select
        m.segment_id,
        avg(c.lifetime_value) as avg_lifetime_value,
        avg(c.total_orders) as avg_total_orders,
        count(case when c.last_seen_at >= current_timestamp - interval '30 day' then 1 end) as active_last_30d
    from memberships m
    left join customer_360 c on m.customer_id = c.customer_id
    group by m.segment_id
)

select
    s.segment_id,
    s.segment_name,
    s.segment_description,
    s.segment_status,
    s.ai_generated,
    s.ai_prompt,
    s.created_by,
    s.created_at,
    s.updated_at,

    s.estimated_count as cached_estimated_count,
    s.last_count_at as cached_last_count_at,
    coalesce(sc.computed_member_count, 0) as computed_member_count,
    sc.last_membership_compute_at,

    coalesce(v.avg_lifetime_value, 0) as avg_lifetime_value,
    coalesce(v.avg_total_orders, 0) as avg_total_orders,
    coalesce(v.active_last_30d, 0) as active_customers_last_30d
from segments s
left join segment_counts sc on s.segment_id = sc.segment_id
left join segment_value v on s.segment_id = v.segment_id
