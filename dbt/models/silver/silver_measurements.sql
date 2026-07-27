with source as (
    select
        cast(s.record_id as varchar) as child_record_id,
        c.school_id,
        c.period,
        cast(s.measurement_date_parsed as timestamp) as measurement_date,
        cast(s.birthday_str_parsed as date) as birth_date,
        try_cast(s.height_cm as double) as height_cm,
        try_cast(s.weight_kg as double) as weight_kg,
        s.measurement_date_issue_flag,
        s.birthday_str_issue_flag
    from {{ ref('stg_bronze_school_submissions') }} s
    inner join {{ ref('silver_child_records') }} c
      on cast(s.record_id as varchar) = c.child_record_id
)
select
    md5(child_record_id || ':' || period) as measurement_id,
    child_record_id,
    school_id,
    period,
    measurement_date,
    case when measurement_date is not null and birth_date is not null
         then date_diff('day', birth_date, cast(measurement_date as date)) / 365.25
    end::double as age_years,
    height_cm,
    weight_kg,
    case when height_cm > 0 then weight_kg / power(height_cm / 100.0, 2) end::double as bmi,
    case
        when measurement_date_issue_flag is not null or birthday_str_issue_flag is not null then 'date_issue'
        when height_cm is null or weight_kg is null then 'missing_measurement'
        when height_cm not between 80 and 200 or weight_kg not between 10 and 100 then 'implausible'
        else 'valid'
    end as measurement_quality_flag
from source
