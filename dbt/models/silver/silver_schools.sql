with ranked as (
    select
        trim(cast(school_id as varchar)) as school_id,
        trim(cast(school_name as varchar)) as school_name,
        nullif(trim(cast(division as varchar)), '') as division,
        nullif(trim(cast(municipality as varchar)), '') as municipality,
        nullif(trim(cast(barangay as varchar)), '') as barangay,
        nullif(trim(cast(urban_rural as varchar)), '') as urban_rural,
        try_cast(treatment_status as bigint) as treatment_status,
        nullif(trim(cast(matched_pair_id as varchar)), '') as matched_pair_id,
        row_number() over (
            partition by trim(cast(school_id as varchar))
            order by ingested_at desc, source_row_number desc
        ) as row_rank
    from {{ ref('stg_bronze_schools') }}
    where nullif(trim(cast(school_id as varchar)), '') is not null
)
select * exclude (row_rank)
from ranked
where row_rank = 1
