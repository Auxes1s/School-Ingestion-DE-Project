select
    coalesce(school_id, 'UNASSIGNED') as school_id,
    coalesce(period, 'all') as period,
    rule_id,
    severity,
    resolved_status,
    count(*)::bigint as issue_count,
    count(distinct record_id)::bigint as affected_record_count,
    max(detected_at) as last_detected_at
from {{ ref('stg_dqa_issues') }}
group by all
