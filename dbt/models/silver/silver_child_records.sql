with schools as (
    select school_id, lower(regexp_replace(trim(school_name), '\\s+', ' ', 'g')) as school_key
    from {{ ref('silver_schools') }}
), cleaned as (
    select
        cast(s.record_id as varchar) as child_record_id,
        coalesce(
            nullif(trim(cast(s.school_id as varchar)), ''),
            nullif(trim(cast(s.school_id_guess as varchar)), ''),
            schools.school_id
        ) as school_id,
        lower(trim(cast(s.period_guess as varchar))) as period,
        nullif(regexp_replace(cast(s.lrn_clean as varchar), '[^0-9]', '', 'g'), '') as lrn_clean,
        nullif(upper(regexp_replace(trim(cast(s.student_name_clean as varchar)), '\\s+', ' ', 'g')), '') as student_name_clean,
        nullif(left(upper(trim(cast(s.student_name_clean as varchar))), 1), '') as first_letter_name,
        case
            when s.birthday_str_parsed is not null then strftime(cast(s.birthday_str_parsed as date), '%Y-%m-%d')
        end as birthday_str,
        case
            when lower(trim(cast(s.sex as varchar))) = 'male' then 'Male'
            when lower(trim(cast(s.sex as varchar))) = 'female' then 'Female'
        end as sex,
        nullif(trim(cast(s.grade as varchar)), '') as grade,
        cast(s.run_id as varchar) as run_id,
        cast(s.source_file_id as varchar) as source_file_id,
        cast(s.source_file_path as varchar) as source_file_path,
        cast(s.source_sheet_name as varchar) as source_sheet_name,
        cast(s.source_row_number as bigint) as source_row_number,
        cast(s.file_hash as varchar) as file_hash,
        cast(s.ingested_at as timestamp) as ingested_at,
        cast(s.raw_payload_json as varchar) as raw_payload_json
    from {{ ref('stg_bronze_school_submissions') }} s
    left join schools
      on lower(regexp_replace(trim(cast(s.school_name as varchar)), '\\s+', ' ', 'g')) = schools.school_key
)
select *
from cleaned
where school_id is not null and period in ('baseline', 'endline')
