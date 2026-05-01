with base as (
    select
        run_id,
        goal,
        recommendation_index,
        name as recommendation_name,
        description as recommendation_description,
        rationale,
        estimated_size,
        potential_impact,
        priority,
        segment_json,
        payload_json,
        created_at
    from ai_audience_recommendations
),
goal_rollup as (
    select
        goal,
        count(*) as recommendation_count,
        sum(case when lower(coalesce(priority, '')) = 'high' then 1 else 0 end) as high_priority_count
    from base
    group by 1
)
select
    b.run_id,
    b.goal,
    b.recommendation_index,
    b.recommendation_name,
    b.recommendation_description,
    b.rationale,
    b.estimated_size,
    b.potential_impact,
    b.priority,
    g.recommendation_count as goal_recommendation_count,
    g.high_priority_count as goal_high_priority_count,
    b.segment_json,
    b.payload_json,
    b.created_at
from base b
left join goal_rollup g on b.goal = g.goal
