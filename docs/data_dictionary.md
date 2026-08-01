# Data dictionary

| Layer | Table | Grain | Purpose |
|---|---|---|---|
| Bronze | `bronze_school_submissions` | source row | Canonical aliases plus source fidelity and date parse provenance |
| Bronze | `bronze_file_manifest` | file version | Hash, status, row counts, and ingestion timestamps |
| Bronze | `bronze_schema_drift_log` | file-column event | Missing and unmapped columns |
| Silver | `silver_child_records` | child record and wave | Standardized linkage identity with provenance |
| Silver | `silver_measurements` | child record and wave | Dates, age, anthropometry, BMI, and flags |
| Silver | `silver_schools` | school | Location, matched pair, and treatment assignment |
| Silver | `silver_allocations` | school-year | Enrollment, allocation, ration, and dilution metrics |
| Silver | `silver_dqa_issues` | detected record-rule pair | Severity, scope, observed value, and resolution state |
| Linkage | `silver_linkage_candidates` | baseline-endline candidate | Method, pass, probability, and weight |
| Linkage | `silver_linkage_results` | resolved candidate | Accepted/review/rejected decision and transfer flag |
| Gold | `gold_evaluation_child_panel` | linked panel child | Privacy-safe baseline/endline analytical record |
| Gold | `gold_dqa_scorecard` | DQA rule | Injected, detected, missed, false positives, sensitivity, precision |
| Gold | `gold_linkage_scorecard` | method-threshold | Precision, recall, F1, match rate, queue size, transfer recall |
| Gold | `gold_school_monitoring_mart` | school | Submission, measurement, linkage, and issue aggregates |
| Gold | `gold_program_exposure_mart` | school-year | Allocation pressure and effective ration |

The executable Pandera schemas in `src/sbfp_platform/contracts.py` are authoritative.
Gold and exports forbid learner names, LRNs, and raw payloads.
The linkage directory also contains `trained_splink_model.json`, the persisted global
model loaded for production candidate scoring.

## Core fields

| Field | Type / values | Layer | Meaning |
|---|---|---|---|
| `source_file_id` | 16-char hex | bronze/silver | Stable hash of repo-relative source path |
| `source_row_number` | integer ≥ 1 | bronze/silver | Data-row position after header/blank-row handling |
| `child_record_id` | 16-char hex | silver | Stable source-file/row identity |
| `period` | `baseline`, `endline` | silver | Program measurement wave |
| `birthday_str` | ISO string, nullable | silver | Parsed birth date for linkage; parse provenance retained |
| `sex` | `Male`, `Female`, null | silver | Normalized submitted value |
| `measurement_date` | timestamp, nullable | silver | Parsed weighing date |
| `height_cm`, `weight_kg` | float, nullable | silver/gold | Anthropometry in metric units |
| `treatment_status` | `0`, `1` | silver/gold | Control/treatment assignment |
| `severity` | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` | DQA/gold | Review urgency |
| `scope` | file/record/child/school/school-period | DQA | Grain a rule can observe |
| `decision` | accepted/review/rejected | linkage | Resolver outcome |
| `match_probability` | float 0–1, nullable | linkage/gold | Splink or deterministic confidence |
| `dilution_ratio` | float | silver/gold | Allocation base divided by current enrollment |
| `has_critical_issue` | boolean | gold panel | Any critical finding on contributing records |

Date columns in bronze also carry `_parsed`, `_parse_rule`, `_parse_confidence`, and
`_issue_flag` companions so ambiguous or impossible inputs are never silently resolved.
