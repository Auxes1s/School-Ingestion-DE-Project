# Data lineage and reconciliation

`source_file_id = SHA256(relative POSIX source path)[:16]`. Data rows are numbered from
one after excluding the header and blank spacer rows. `record_id` is the same stable hash
over `source_file_id|source_row_number`. The generator assigns IDs only after inserting
duplicates and finalizing row order; ingestion independently derives the identical IDs.

Reconciliation checkpoints:

1. File manifest `rows_read` and `rows_written` explain every source file.
2. Bronze part row counts reconcile to active ingested manifest versions.
3. Silver child records retain source file and row lineage.
4. Accepted links are one-to-one; the gold panel has one row per accepted link.
5. DQA scorecard counts reconcile detectable injected defects to `(record_id, rule_id)`
   detections; non-targeted defects never inflate the denominator.
6. Linkage recall uses retained truth links only, while match rate uses baseline records.
