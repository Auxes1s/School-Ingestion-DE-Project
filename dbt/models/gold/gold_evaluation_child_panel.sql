with accepted as (
    select * from {{ ref('stg_linkage_results') }} where decision = 'accepted'
), critical as (
    select record_id, true as has_critical_issue
    from {{ ref('stg_dqa_issues') }}
    where severity = 'CRITICAL' and resolved_status = 'unresolved' and record_id is not null
    group by record_id
)
select
    cast(l.link_id as varchar) as panel_child_id,
    b.school_id,
    s.treatment_status,
    coalesce(b.sex, e.sex) as sex,
    b.grade as grade_baseline,
    e.grade as grade_endline,
    mb.height_cm as height_cm_baseline,
    me.height_cm as height_cm_endline,
    mb.weight_kg as weight_kg_baseline,
    me.weight_kg as weight_kg_endline,
    mb.bmi as bmi_baseline,
    me.bmi as bmi_endline,
    date_diff('day', cast(mb.measurement_date as date), cast(me.measurement_date as date))::double as elapsed_days,
    cast(l.method as varchar) as link_method,
    try_cast(l.match_probability as double) as link_probability,
    coalesce(cb.has_critical_issue, false) or coalesce(ce.has_critical_issue, false) as has_critical_issue
from accepted l
inner join {{ ref('silver_child_records') }} b on l.baseline_record_id = b.child_record_id
inner join {{ ref('silver_child_records') }} e on l.endline_record_id = e.child_record_id
inner join {{ ref('silver_schools') }} s on b.school_id = s.school_id
left join {{ ref('silver_measurements') }} mb on b.child_record_id = mb.child_record_id
left join {{ ref('silver_measurements') }} me on e.child_record_id = me.child_record_id
left join critical cb on b.child_record_id = cb.record_id
left join critical ce on e.child_record_id = ce.record_id
