select * from {{ parquet_scan('bronze_program_allocations') }}
