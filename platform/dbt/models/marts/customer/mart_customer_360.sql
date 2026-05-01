with profiles as (
    select * from {{ ref('stg_customer_profiles') }}
),

attr as (
    select * from {{ ref('int_customer_attributes_pivot') }}
),

events as (
    select
        customer_id,
        count(*) as total_events,
        max(occurred_at) as last_event_at
    from {{ ref('stg_customer_events') }}
    group by customer_id
)

select
    p.customer_id,
    p.external_id,
    p.email,
    p.phone,
    p.first_name,
    p.last_name,
    trim(coalesce(p.first_name, '') || ' ' || coalesce(p.last_name, '')) as full_name,

    a.city,
    a.state,
    a.country,
    a.acquisition_source,
    a.gender,
    a.support_sentiment,
    a.signup_date_raw as signup_date,
    a.last_order_date_raw as last_order_date,

    coalesce(a.lifetime_value, 0) as lifetime_value,
    coalesce(a.total_orders, 0) as total_orders,
    coalesce(a.avg_order_value, 0) as avg_order_value,
    coalesce(a.support_ticket_count, 0) as support_ticket_count,

    coalesce(e.total_events, 0) as total_events,
    e.last_event_at,

    p.source_count,
    p.first_seen_at,
    p.last_seen_at,
    p.last_synced_at,
    p.created_at,
    p.updated_at
from profiles p
left join attr a on p.customer_id = a.customer_id
left join events e on p.customer_id = e.customer_id
