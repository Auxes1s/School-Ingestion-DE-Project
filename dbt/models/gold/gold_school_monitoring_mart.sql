with children as (
    select
        school_id,
        count(*) filter (where period = 'baseline')::bigint as baseline_records,
        count(*) filter (where period = 'endline')::bigint as endline_records
    from {{ ref('silver_child_records') }} group by school_id
), issues as (
    select school_id, count(*)::bigint as dqa_issue_count,
           count(*) filter (where severity = 'CRITICAL')::bigint as critical_issue_count
    from {{ ref('stg_dqa_issues') }} where school_id is not null group by school_id
), links as (
    select school_id, count(*) filter (where decision = 'accepted')::bigint as accepted_link_count
    from {{ ref('stg_linkage_results') }} where school_id is not null group by school_id
)
select
    s.school_id,
    s.school_name,
    s.division,
    s.municipality,
    s.urban_rural,
    s.treatment_status,
    coalesce(c.baseline_records, 0)::bigint as baseline_records,
    coalesce(c.endline_records, 0)::bigint as endline_records,
    coalesce(l.accepted_link_count, 0)::bigint as accepted_link_count,
    coalesce(i.dqa_issue_count, 0)::bigint as dqa_issue_count,
    coalesce(i.critical_issue_count, 0)::bigint as critical_issue_count,
    a.dilution_ratio,
    a.effective_rice_kg_per_child,
    a.delivery_timing_flag
from {{ ref('silver_schools') }} s
left join children c using (school_id)
left join issues i using (school_id)
left join links l using (school_id)
left join {{ ref('silver_allocations') }} a using (school_id)
