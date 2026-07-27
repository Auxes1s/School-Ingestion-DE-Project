select
    a.school_id,
    s.school_name,
    s.treatment_status,
    a.school_year,
    a.allocated_children,
    a.current_enrollment,
    a.nominal_rice_kg_per_child,
    a.effective_rice_kg_per_child,
    a.dilution_ratio,
    a.delivery_tranche_count,
    a.delivery_timing_flag,
    (a.allocated_children < a.current_enrollment) as allocation_shortfall_flag
from {{ ref('silver_allocations') }} a
inner join {{ ref('silver_schools') }} s using (school_id)
