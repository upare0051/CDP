with ranked_insights as (
    select
        customer_id,
        external_id,
        summary,
        churn_score,
        churn_level,
        engagement_score,
        customer_segment,
        next_best_actions_json,
        created_at,
        row_number() over (
            partition by customer_id
            order by created_at desc
        ) as row_num
    from ai_customer_insights
    where insight_kind = 'profile_analysis'
),
latest as (
    select *
    from ranked_insights
    where row_num = 1
)
select
    customer_id,
    external_id,
    summary,
    churn_score,
    churn_level,
    engagement_score,
    customer_segment,
    next_best_actions_json,
    case
        when churn_score >= 0.6 then 'priority_followup'
        when churn_score >= 0.2 then 'monitor'
        else 'healthy'
    end as cs_action_bucket,
    created_at as insight_created_at
from latest
