select
    treatment_status,
    count(*)::bigint as school_count,
    sum(baseline_records)::bigint as baseline_record_count,
    sum(endline_records)::bigint as endline_record_count,
    sum(accepted_link_count)::bigint as accepted_link_count,
    sum(dqa_issue_count)::bigint as dqa_issue_count,
    sum(critical_issue_count)::bigint as critical_issue_count,
    avg(dilution_ratio)::double as mean_dilution_ratio,
    avg(effective_rice_kg_per_child)::double as mean_effective_rice_kg_per_child
from {{ ref('gold_school_monitoring_mart') }}
group by treatment_status
