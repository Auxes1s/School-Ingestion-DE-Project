select 1
where (select count(*) from {{ ref('silver_child_records') }})
   <> (select count(*) from {{ ref('silver_measurements') }})
