select * from {{ parquet_scan('bronze_enrollment_snapshots') }}
