# ADR-001: Local DuckDB and Parquet lakehouse

**Decision:** Use Parquet for durable layers and DuckDB/dbt for analytics.

The public demo must be reproducible without accounts or paid infrastructure. This stack
retains columnar storage, SQL transformations, pushdown, testable models, and portable
artifacts. It gives up managed concurrency and cloud operations, which are not required
for a single-machine portfolio workload.
