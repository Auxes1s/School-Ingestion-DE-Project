# Data contracts

The authoritative runtime contracts are Pandera schemas in
`src/sbfp_platform/contracts.py`. dbt repeats warehouse-facing constraints as schema and
relationship tests, and CI runs both layers.

Contract rules:

- canonical names and types cannot change across slices without updating the design;
- every bronze record carries file, sheet, row, hash, run, ingestion time, and raw
  payload provenance;
- child periods are `baseline` or `endline`, sex values are `Male` or `Female`, and
  treatment is binary;
- linkage candidates identify benchmark and Splink pairs; accepted production
  results come only from the trained Splink resolver;
  results are globally one-to-one;
- DQA rules use configured severities/scopes and unique `(record, rule)` issue IDs;
- truth tables are writable by generation and readable only by evaluation;
- gold schemas and exports reject names, learner numbers, and raw source payloads.

Dates accept ISO, month-first and day-first slash dates, Excel serials, and timestamp-
suffixed values. Parsing records the rule, confidence, and anomaly flag; plausible birth
years come from project configuration.

Backward compatibility is intentionally strict for table and column names. New nullable
columns may be added to non-strict schemas; renames and type changes require a migration
and updated tests.
