select * from {{ parquet_scan('bronze_school_masterlist') }}
