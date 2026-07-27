with schools as (
    select school_id, lower(regexp_replace(trim(school_name), '\\s+', ' ', 'g')) as school_key
    from {{ ref('silver_schools') }}
), enrollment as (
    select
        lower(regexp_replace(trim(cast(school_name as varchar)), '\\s+', ' ', 'g')) as school_key,
        trim(cast(school_year as varchar)) as school_year,
        try_cast(current_enrollment as double) as current_enrollment
    from {{ ref('stg_bronze_enrollment') }}
), allocations as (
    select
        lower(regexp_replace(trim(cast(school_name as varchar)), '\\s+', ' ', 'g')) as school_key,
        trim(cast(school_year as varchar)) as school_year,
        try_cast(allocated_children as double) as allocated_children,
        try_cast(delivery_tranche_count as double) as delivery_tranche_count
    from {{ ref('stg_bronze_allocations') }}
)
select
    schools.school_id,
    allocations.school_year,
    allocations.allocated_children,
    enrollment.current_enrollment,
    cast({{ var('nominal_rice_kg_per_child') }} as double) as nominal_rice_kg_per_child,
    cast({{ var('nominal_rice_kg_per_child') }} as double)
        * least(1.0, allocations.allocated_children / nullif(enrollment.current_enrollment, 0))
        as effective_rice_kg_per_child,
    allocations.allocated_children / nullif(enrollment.current_enrollment, 0) as dilution_ratio,
    allocations.delivery_tranche_count,
    case
        when allocations.delivery_tranche_count is null then 'unknown'
        when allocations.delivery_tranche_count < 2 then 'delayed_or_incomplete'
        else 'on_schedule'
    end as delivery_timing_flag
from allocations
inner join schools using (school_key)
left join enrollment using (school_key, school_year)
