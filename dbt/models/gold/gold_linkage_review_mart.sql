select
    cast(r.link_id as varchar) as link_id,
    cast(r.baseline_record_id as varchar) as baseline_record_id,
    cast(r.endline_record_id as varchar) as endline_record_id,
    cast(r.school_id as varchar) as school_id,
    cast(r.method as varchar) as method,
    try_cast(r.match_probability as double) as match_probability,
    cast(r.decision as varchar) as decision,
    cast(r.review_reason as varchar) as review_reason,
    cast(r.transferred_flag as boolean) as transferred_flag,
    coalesce(c.candidate_count, 0)::bigint as candidate_count
from {{ ref('stg_linkage_results') }} r
left join (
    select baseline_record_id, count(*) as candidate_count
    from {{ ref('stg_linkage_candidates') }}
    group by baseline_record_id
) c using (baseline_record_id)
