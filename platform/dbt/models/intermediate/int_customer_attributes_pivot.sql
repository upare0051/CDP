with attributes as (
    select *
    from {{ ref('stg_customer_attributes') }}
),

pivoted as (
    select
        customer_id,

        max(case when attribute_name = 'city' then attribute_value end) as city,
        max(case when attribute_name = 'state' then attribute_value end) as state,
        max(case when attribute_name = 'country' then attribute_value end) as country,
        max(case when attribute_name = 'acquisition_source' then attribute_value end) as acquisition_source,
        max(case when attribute_name = 'gender' then attribute_value end) as gender,
        max(case when attribute_name = 'signup_date' then attribute_value end) as signup_date_raw,
        max(case when attribute_name = 'last_order_date' then attribute_value end) as last_order_date_raw,
        max(case when attribute_name = 'support_sentiment' then attribute_value end) as support_sentiment,

        max(case when attribute_name = 'lifetime_value' then {{ safe_to_numeric('attribute_value') }} end) as lifetime_value,
        max(case when attribute_name = 'total_orders' then {{ safe_to_numeric('attribute_value') }} end) as total_orders,
        max(case when attribute_name = 'avg_order_value' then {{ safe_to_numeric('attribute_value') }} end) as avg_order_value,
        max(case when attribute_name = 'support_ticket_count' then {{ safe_to_numeric('attribute_value') }} end) as support_ticket_count
    from attributes
    group by customer_id
)

select * from pivoted
