# Technical Design Specification
# Public Sector Data Platform for School Feeding Evaluation

- **Project name:** `school-feeding-data-platform`
- **Project type:** Public portfolio data engineering project
- **Primary domain:** Public-sector monitoring and evaluation, school feeding, education, nutrition
- **Data release model:** Fully synthetic, privacy-safe, structurally realistic
- **Primary audience:** Data engineering recruiters, public-sector data teams, M&E teams, analytics engineers, evaluation specialists
- **Implementation language:** Python and SQL
- **Document version:** v2.0
- **Status:** Implemented and locally verified
- **Last verified:** 2026-07-31

---

## 1. Executive Summary

This project implements a public, privacy-safe data engineering platform that simulates how messy school-based feeding monitoring records are converted into trusted, analysis-ready data products.

The platform uses synthetic data modeled after real administrative data challenges: school Excel submissions, baseline and endline child measurements, school-level program assignment, enrollment snapshots, allocation files, date-format inconsistencies, duplicate learners, missing fields, measurement outliers, and baseline-to-endline linkage issues.

The implementation showcases production-grade data engineering skills across the full data engineering lifecycle:

1. **Generation** - synthetic source systems and raw school submissions.
2. **Storage** - local lakehouse using Parquet and DuckDB.
3. **Ingestion** - idempotent batch ingestion from messy Excel and CSV files.
4. **Transformation** - bronze, silver, and gold modeling using SQL and Python.
5. **Serving** - analytics-ready marts, dashboards, documentation, and exports.

The platform will also demonstrate cross-cutting engineering capabilities:

- Data quality management
- Metadata and lineage
- Orchestration
- Observability
- Testing
- Privacy and security-by-design
- CI/CD
- Documentation
- Reproducible local deployment

The result is a small but credible public-sector data platform rather than a one-off data cleaning notebook.

### 1.1 Verified Reference Run

The fixed-seed `tiny` profile was executed through the complete CLI and Dagster graphs. It produced 1,918 baseline/endline source records across five source groups and 13 files. All 21 configured DQA rules ran, detecting 1,433 of 1,579 targeted injected defects (90.75%). At the configured 0.10 operating threshold, the exact-rule benchmark reached 63.18% recall. The production resolver—one globally trained, persisted, and reloaded Splink model—accepted 812 true pairs with 100% precision, 92.27% recall, 95.98% F1, and 73.08% recall among records that moved between source groups. Splink accepted 256 more true links overall than exact matching.

Local verification completed with 407 passing tests, Ruff lint/format checks, privacy scanning, dbt builds, Streamlit AppTest, and the tiny full refresh. The Docker image is exercised by GitHub Actions because Docker is unavailable on the development host. No dashboard screenshot is claimed; all six views are verified by Streamlit AppTest without fabricating an image.

---

## 2. Guiding Expert Perspectives

This design assumes the combined perspective of the following subject matter experts:

- **Data engineer:** designs robust ingestion, storage, transformation, orchestration, and serving layers.
- **Analytics engineer:** builds tested, documented, reusable data models and marts.
- **M&E data systems specialist:** ensures the data products support evaluation, monitoring, reporting, and auditability.
- **Data governance and privacy reviewer:** ensures no confidential learner information is exposed and that synthetic data is clearly separated from real records.
- **Impact evaluation analyst:** ensures the final panel preserves school-level assignment, baseline-endline structure, and measurement flags needed for downstream causal analysis.

---

## 3. Problem Statement

School-based feeding programs rely on administrative records collected across many schools, divisions, forms, and reporting periods. These records are often stored as spreadsheets and may contain:

- inconsistent column names
- inconsistent date formats
- duplicate learners
- missing learner identifiers
- spelling variation in names
- implausible height or weight values
- school name inconsistencies
- baseline and endline records that do not link cleanly
- mismatches between program allocation counts and current enrollment
- late or incomplete submissions
- weak metadata and limited lineage

For evaluation and monitoring, the data system must produce a trusted child-level panel and school-level monitoring marts. The platform must make quality problems visible rather than silently hiding them.

The public version uses fully synthetic data while preserving the engineering shape of the real problem.

---

## 4. Project Objectives

### 4.1 Primary Objective

Build a reproducible data platform that transforms raw, messy, synthetic school feeding records into validated and documented data products for analysis, monitoring, and evaluation.

### 4.2 Technical Objectives

The project should demonstrate the ability to:

1. Generate realistic synthetic source data with controlled data quality defects.
2. Ingest heterogeneous school submissions into a bronze lakehouse layer.
3. Standardize records into silver tables with strong schema validation.
4. Build gold data marts for evaluation, school monitoring, and data quality reporting.
5. Link baseline and endline child records using deterministic and probabilistic matching.
6. Track data lineage from raw files to final analytical outputs.
7. Orchestrate the pipeline with observable, retryable, modular tasks.
8. Run automated tests and validation checks through CI/CD.
9. Serve trusted outputs through SQL views, dashboard pages, and export files.
10. Document the full system in a way that is understandable to technical and nontechnical reviewers.

### 4.3 Portfolio Objectives

The final public repository should show that the builder can:

- design a data platform, not merely clean a dataset
- implement DataOps practices
- build an audit-friendly administrative data pipeline
- protect sensitive data through synthetic data and privacy controls
- communicate technical design clearly
- support downstream analytics and impact evaluation

---

## 5. Non-Goals

The public project will not:

1. Publish real learner data.
2. Publish real school-level confidential records.
3. Claim to reproduce official impact estimates.
4. Replace a formal government data system.
5. Build a full cloud production deployment in the MVP.
6. Build machine learning models as the main focus.
7. Prioritize causal inference over data engineering.

The causal evaluation context will be used only to define realistic downstream data requirements.

---

## 6. Data Engineering Lifecycle Mapping

The platform will be explicitly organized around the data engineering lifecycle.

| Lifecycle stage | Platform implementation | Main outputs |
|---|---|---|
| Generation | Synthetic school submissions, enrollment snapshots, program allocation files, treatment assignment files | Raw synthetic Excel and CSV files |
| Storage | Bronze, silver, and gold lakehouse folders in Parquet, queryable through DuckDB | Versioned local analytical lakehouse |
| Ingestion | Batch file ingestion with manifests, hashes, schema drift capture, and error handling | Bronze tables and ingestion metadata |
| Transformation | Standardization, validation, deduplication, linkage, z-score placeholders, dimensional modeling | Silver normalized tables and gold marts |
| Serving | Streamlit dashboard, SQL views, data documentation, HTML reports, export files | DQA command center, evaluation panel, monitoring marts |

The undercurrents will be built directly into the design:

| Undercurrent | Platform implementation |
|---|---|
| Security | synthetic data only, PII masking design, secret-free repo, privacy threat model |
| Data management | schema registry, data dictionary, lineage, ownership metadata |
| DataOps | orchestration, logging, observability, CI/CD, automated validation |
| Data architecture | lakehouse pattern, bronze-silver-gold layers, modular components |
| Orchestration | Dagster or Prefect assets and jobs |
| Software engineering | package structure, tests, linting, type hints, reproducible setup |

---

## 7. High-Level Architecture

```text
Synthetic Source Systems
    |
    |-- School Excel submissions
    |-- Enrollment snapshots
    |-- Program allocation files
    |-- School masterlist
    |-- Treatment assignment file
    |-- Measurement device logs
    |
    v
Bronze Layer
    |
    |-- Raw ingested records
    |-- File manifests
    |-- Schema drift logs
    |-- Ingestion run metadata
    |
    v
Silver Layer
    |
    |-- Standardized child records
    |-- Standardized school records
    |-- Standardized measurement records
    |-- Standardized enrollment records
    |-- Standardized program allocation records
    |-- DQA issue tables
    |-- Linkage candidate tables
    |
    v
Gold Layer
    |
    |-- Evaluation-ready child panel
    |-- School monitoring mart
    |-- Data quality mart
    |-- Linkage review mart
    |-- Program exposure and dilution mart
    |
    v
Serving Layer
    |
    |-- Streamlit command center
    |-- HTML DQA report
    |-- SQL views
    |-- CSV and Parquet exports
    |-- Data documentation site
```

---

## 8. Recommended Technology Stack

### 8.1 Core Stack

| Component | Recommended tool | Purpose |
|---|---|---|
| Programming | Python 3.11+ | Main pipeline language |
| SQL engine | DuckDB | Local analytical warehouse |
| File format | Parquet | Columnar lakehouse storage |
| Orchestration | Dagster, preferred, or Prefect | Pipeline assets, scheduling, dependencies |
| Transformations | dbt-core with DuckDB adapter, or SQLMesh | SQL modeling and documentation |
| Data validation | Pandera for Python, dbt tests for SQL, optional Great Expectations | Schema and data quality checks |
| Record linkage | Splink | Probabilistic linkage |
| Dashboard | Streamlit | Public command center |
| Testing | pytest | Unit and integration tests |
| Linting and formatting | ruff | Code quality |
| Environment | uv | Fast Python environment management |
| Containerization | Docker | Reproducible local run |
| CI/CD | GitHub Actions | Automated test and sample pipeline run |

### 8.2 Why This Stack

This stack is intentionally modern but not excessive.

- **DuckDB + Parquet** demonstrates lakehouse-style analytics without needing paid cloud infrastructure.
- **Dagster or Prefect** demonstrates orchestration and observability without requiring Airflow overhead.
- **dbt-core** demonstrates analytics engineering, tested transformations, documentation, and lineage.
- **Pandera and dbt tests** demonstrate data quality as code.
- **Splink** demonstrates real-world entity resolution.
- **Streamlit** demonstrates serving and stakeholder-facing outputs.
- **GitHub Actions and Docker** demonstrate reproducibility and delivery discipline.

---

## 9. Repository Structure

The implemented repository is intentionally more compact than the conceptual decomposition below. The as-built top level is:

```text
school-feeding-data-platform/
├── configs/                 # scale, paths, schema aliases, DQA/linkage policy
├── src/sbfp_platform/       # generator, ingestion, validation, linkage, transforms, evaluation
├── dbt/                     # staging, four silver models, six gold models, tests
├── orchestration/           # one Dagster definitions module with eight assets
├── dashboards/              # six-view Streamlit command center
├── docs/                    # architecture, contracts, lineage, privacy, DQA, six ADRs
├── tests/                   # unit, integration, privacy, and regression tests
├── data/                    # generated and Git-ignored source/lakehouse artifacts
├── outputs/                 # generated and Git-ignored exports and HTML reports
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── README.md
```

The following tree is the logical component map from the design phase, not a literal one-file-per-component inventory. Related operations were consolidated where a smaller module provided a clearer public implementation; unimplemented aspirational entries such as separate masking, incident-response, Quarto, and sample-workflow files are not part of v2.0.

```text
school-feeding-data-platform/
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── Makefile
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── configs/
│   ├── project.yml
│   ├── paths.yml
│   ├── schema_registry.yml
│   ├── dqa_rules.yml
│   ├── linkage_rules.yml
│   └── synthetic_data.yml
│
├── data/
│   ├── synthetic_raw/
│   │   ├── baseline/
│   │   ├── endline/
│   │   ├── enrollment/
│   │   ├── allocation/
│   │   └── reference/
│   ├── lakehouse/
│   │   ├── bronze/
│   │   ├── silver/
│   │   └── gold/
│   └── external/
│       └── README.md
│
├── src/
│   └── sbfp_platform/
│       ├── __init__.py
│       ├── cli.py
│       ├── synthetic/
│       │   ├── generate_children.py
│       │   ├── generate_schools.py
│       │   ├── generate_measurements.py
│       │   ├── inject_quality_issues.py
│       │   └── write_source_files.py
│       ├── ingestion/
│       │   ├── discover_files.py
│       │   ├── read_excel.py
│       │   ├── standardize_columns.py
│       │   ├── parse_dates.py
│       │   ├── write_bronze.py
│       │   └── manifest.py
│       ├── validation/
│       │   ├── schema_checks.py
│       │   ├── completeness_checks.py
│       │   ├── range_checks.py
│       │   ├── consistency_checks.py
│       │   ├── duplicate_checks.py
│       │   ├── measurement_checks.py
│       │   └── issue_registry.py
│       ├── linkage/
│       │   ├── deterministic.py
│       │   ├── splink_config.py
│       │   ├── probabilistic.py
│       │   ├── review_queue.py
│       │   └── link_baseline_endline.py
│       ├── transforms/
│       │   ├── build_silver.py
│       │   ├── build_gold.py
│       │   └── build_exports.py
│       ├── observability/
│       │   ├── run_logger.py
│       │   ├── metrics.py
│       │   ├── anomaly_checks.py
│       │   └── freshness.py
│       ├── privacy/
│       │   ├── pii_scanner.py
│       │   └── masking.py
│       └── utils/
│           ├── io.py
│           ├── hashing.py
│           ├── dates.py
│           └── logging.py
│
├── orchestration/
│   └── dagster_project/
│       ├── definitions.py
│       ├── assets/
│       ├── jobs/
│       └── schedules/
│
├── dbt/
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── bronze/
│   │   ├── silver/
│   │   ├── gold/
│   │   └── marts/
│   ├── tests/
│   ├── macros/
│   └── docs/
│
├── dashboards/
│   └── streamlit_app.py
│
├── reports/
│   ├── data_quality_report.qmd
│   ├── pipeline_run_summary.qmd
│   └── evaluation_readiness_report.qmd
│
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── data_contracts.md
│   ├── data_lineage.md
│   ├── dqa_rules.md
│   ├── privacy_and_synthetic_data.md
│   ├── operating_model.md
│   ├── incident_response.md
│   ├── portfolio_walkthrough.md
│   └── decisions/
│       ├── ADR-001-lakehouse-local-first.md
│       ├── ADR-002-duckdb-parquet.md
│       ├── ADR-003-dagster-vs-prefect.md
│       └── ADR-004-synthetic-data-release.md
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── outputs/
    ├── exports/
    ├── lineage/
    └── reports/
```

---

## 10. Data Domains

The platform will model five core domains.

### 10.1 School Domain

Represents schools, location, treatment assignment, administrative grouping, and school characteristics.

Example fields:

| Field | Type | Description |
|---|---|---|
| `school_id` | string | Stable synthetic school identifier |
| `school_name` | string | Synthetic school name |
| `division` | string | Administrative division |
| `municipality` | string | Municipality |
| `barangay` | string | Barangay |
| `urban_rural` | string | Urban or rural classification |
| `treatment_status` | integer | 1 if SBFP school, 0 otherwise |
| `matched_pair_id` | string | Synthetic matched-pair grouping |

### 10.2 Child Domain

Represents child-level identity, demographics, and stable attributes.

Example fields:

| Field | Type | Description |
|---|---|---|
| `child_record_id` | string | Stable source-record identity |
| `lrn_clean` | string | Cleaned synthetic learner identifier, retained only through silver |
| `student_name_clean` | string | Standardized synthetic name, retained only through silver |
| `first_letter_name` | string | Blocking key derived from the standardized name |
| `sex` | string | Male or Female |
| `birthday_str` | string | ISO-formatted parsed birth date used for linkage |
| `grade` | string | Submitted grade for the record's wave |

### 10.3 Measurement Domain

Represents baseline and endline anthropometric records.

Example fields:

| Field | Type | Description |
|---|---|---|
| `measurement_id` | string | Unique measurement record |
| `child_record_id` | string | Parent silver child record |
| `school_id` | string | School identifier |
| `period` | string | baseline or endline |
| `measurement_date` | date | Date of weighing or measuring |
| `age_years` | numeric | Age at measurement |
| `height_cm` | numeric | Height in centimeters |
| `weight_kg` | numeric | Weight in kilograms |
| `bmi` | numeric | Body mass index |
| `measurement_quality_flag` | string | Flag summary |

### 10.4 Program Domain

Represents program allocation, treatment exposure, and enrollment pressure.

Example fields:

| Field | Type | Description |
|---|---|---|
| `school_id` | string | School identifier |
| `school_year` | string | School year |
| `allocated_children` | integer | Children used for allocation planning |
| `current_enrollment` | integer | Current enrollment count |
| `nominal_rice_kg_per_child` | numeric | Nominal ration |
| `effective_rice_kg_per_child` | numeric | Synthetic effective ration after dilution |
| `dilution_ratio` | numeric | Allocation base divided by current enrollment |
| `dilution_exposure` | numeric | Bounded dilution measure |
| `delivery_tranche_count` | integer | Number of delivery tranches |
| `delivery_timing_flag` | string | On-time, delayed, incomplete, unknown |

### 10.5 Data Quality Domain

Represents row-level, field-level, file-level, and school-level issues.

Example fields:

| Field | Type | Description |
|---|---|---|
| `issue_id` | string | Unique issue ID |
| `run_id` | string | Pipeline run ID |
| `source_file_id` | string | Source file identifier |
| `school_id` | string | School identifier |
| `record_id` | string | Affected record |
| `field_name` | string | Affected field |
| `issue_type` | string | Type of issue |
| `severity` | string | CRITICAL, HIGH, MEDIUM, LOW |
| `issue_message` | string | Human-readable issue description |
| `suggested_action` | string | Recommended review action |
| `resolved_status` | string | unresolved, accepted, corrected, suppressed |

---

## 11. Lakehouse Layer Design

### 11.1 Bronze Layer

The bronze layer stores raw ingested data with minimal transformation.

Purpose:

- preserve source fidelity
- capture file metadata
- support audit and rerun
- allow schema drift inspection
- avoid silent data loss

Example tables:

| Table | Description |
|---|---|
| `bronze_school_submissions` | Raw child-level records from school files |
| `bronze_enrollment_snapshots` | Raw enrollment files |
| `bronze_program_allocations` | Raw program allocation files |
| `bronze_school_masterlist` | Raw school reference data |
| `bronze_file_manifest` | One row per ingested file |
| `bronze_schema_drift_log` | Unexpected, missing, or renamed columns |
| `bronze_ingestion_errors` | Files or rows that failed ingestion |

Bronze records must include:

- `run_id`
- `source_file_id`
- `source_file_path`
- `source_sheet_name`
- `source_row_number`
- `file_hash`
- `ingested_at`
- `raw_payload_json`

### 11.2 Silver Layer

The silver layer stores cleaned, standardized, and validated entities.

Purpose:

- enforce schema
- standardize names and dates
- normalize school and child entities
- detect duplicates
- produce linkage-ready records
- retain quality flags

Example tables:

| Table | Description |
|---|---|
| `silver_child_records` | Standardized child records by period |
| `silver_measurements` | Standardized anthropometric measurements |
| `silver_schools` | Standardized school master data |
| `silver_enrollment` | Standardized enrollment snapshots |
| `silver_allocations` | Standardized program allocation records |
| `silver_dqa_issues` | Row and field-level quality issues |
| `silver_linkage_candidates` | Candidate baseline-endline pairs |
| `silver_linkage_results` | Accepted and rejected links |

### 11.3 Gold Layer

The gold layer stores curated data products for downstream users.

Purpose:

- serve evaluation analysts
- serve monitoring dashboards
- serve DQA reviewers
- serve public documentation

Example tables:

| Table | Description |
|---|---|
| `gold_evaluation_child_panel` | Analysis-ready baseline-endline child panel |
| `gold_school_monitoring_mart` | School-level monitoring and program exposure metrics |
| `gold_dqa_command_center` | Aggregated DQA indicators by school and period |
| `gold_linkage_review_mart` | Match confidence and review needs |
| `gold_program_exposure_mart` | Allocation, enrollment, and dilution indicators |
| `gold_public_dashboard_metrics` | Dashboard-ready aggregate metrics |

---

## 12. Data Model

### 12.1 Conceptual Model

```text
School
  ├── has many Child Records
  ├── has many Measurements
  ├── has many Enrollment Snapshots
  ├── has many Program Allocation Records
  └── has many DQA Issues

Child
  ├── has baseline Measurement
  ├── has endline Measurement
  ├── belongs to School
  └── has Linkage Result

Program Allocation
  ├── belongs to School
  └── contributes to Program Exposure Mart

DQA Issue
  ├── belongs to Source File
  ├── may belong to School
  ├── may belong to Child
  └── may belong to Measurement
```

### 12.2 Dimensional Model

The gold layer uses a dimensional model.

#### Conceptual Fact Grains

These grains guide the gold marts but are not materialized as separate `fact_*` and `dim_*` tables in v2.0; the local demo keeps four silver and six gold models easier to inspect.

| Table | Grain |
|---|---|
| `fact_measurement` | One row per child-period measurement |
| `fact_school_submission` | One row per school-period submission |
| `fact_program_allocation` | One row per school-year allocation |
| `fact_dqa_issue` | One row per detected quality issue |
| `fact_linkage_candidate` | One row per baseline-endline candidate pair |

#### Dimension Tables

| Table | Description |
|---|---|
| `dim_child` | Stable child attributes |
| `dim_school` | School attributes |
| `dim_time` | Date and school-year calendar |
| `dim_program` | Program assignment and implementation attributes |
| `dim_location` | Division, municipality, barangay |
| `dim_issue_type` | Data quality issue taxonomy |

#### Marts

| Mart | Main users |
|---|---|
| `mart_evaluation_panel` | Evaluation analysts |
| `mart_school_monitoring` | Program managers |
| `mart_data_quality` | Data engineers and M&E officers |
| `mart_linkage_review` | Data reviewers |
| `mart_public_dashboard` | Portfolio viewers |

---

## 13. Synthetic Data Design

### 13.1 Synthetic Source Systems

The implemented generator produces:

1. School masterlist
2. Treatment assignment
3. Baseline child measurement files
4. Endline child measurement files
5. Enrollment snapshots
6. Program allocation files
7. File modification timestamps that exercise submission-timeliness rules

Measurement equipment is represented through measurement-quality defects rather than a separate source system. File manifests supply submission and ingestion metadata; no separate reporting-log file is generated.

### 13.2 Synthetic Data Scale

The committed scale profiles are:

| Profile | Divisions | Municipalities | Schools | Children | Use |
|---|---:|---:|---:|---:|---|
| `tiny` | 1 | 2 | 5 | 1,000 | CI and integration tests |
| `demo` | 3 | 20 | 40 | 12,000 | Default local showcase |
| `large` | 3 | 20 | 150 | 50,000 | Opt-in scaling run |

Baseline retention is 88%, so endline counts are lower than child counts before duplicate and defect injection. Raw file counts depend on profile and `schools_per_file`; the verified tiny run writes 13 files.

### 13.3 Controlled Data Defects

The generator will intentionally inject issues to test the pipeline.

| Issue class | Examples |
|---|---|
| Schema drift | `Date of Birth` vs `BIRTH_DATE`, `Weight` vs `Weight (kg)` |
| Date errors | DD/MM/YYYY ambiguity, Excel serial dates, impossible dates |
| Missingness | missing LRN, missing measurement date, missing sex |
| Duplicate records | repeated child rows, same LRN with name variation |
| Linkage ambiguity | name spelling changes, transfer schools, missing LRN |
| Measurement outliers | implausible height, implausible weight, extreme z-scores |
| Consistency issues | child sex changes across waves, birthdate mismatch |
| Enrollment mismatch | allocation count lower than current enrollment |
| Late submission | endline files submitted after expected window |
| School name drift | spelling variation in school names |

### 13.4 Synthetic Data Privacy Rules

Although the data are synthetic, the project should behave as if data were sensitive.

Rules:

1. Do not use real learner names.
2. Do not use real LRNs.
3. Do not use real home addresses.
4. Do not include phone numbers.
5. Do not include real school-level confidential observations.
6. Clearly label all public data as synthetic.
7. Include a privacy note in every public data folder.
8. Add a PII scanner to prevent accidental commits of sensitive-looking fields.

---

## 14. Ingestion Design

### 14.1 File Discovery

The ingestion engine will recursively scan configured folders.

Inputs:

```text
data/synthetic_raw/baseline/
data/synthetic_raw/endline/
data/synthetic_raw/enrollment/
data/synthetic_raw/allocation/
data/synthetic_raw/reference/
```

Each discovered file receives:

- `source_file_id`
- `source_file_path`
- `file_name`
- `file_type`
- `file_hash`
- `file_size_bytes`
- `modified_at`
- `discovered_at`
- `school_id_guess`
- `period_guess`

### 14.2 Idempotent Ingestion

A file should not be duplicated when rerun.

Rules:

1. Compute file hash before ingestion.
2. If file hash already exists for a completed run, skip unless `force=true`.
3. If file path exists but hash changed, ingest as a new version.
4. Preserve old versions for audit.
5. Write all run activity to `bronze_file_manifest`.

### 14.3 Schema Drift Handling

The ingestion engine should not fail immediately on unexpected columns. It should:

1. Map known column aliases to canonical names.
2. Store unmapped columns in `raw_payload_json`.
3. Log unexpected columns to `bronze_schema_drift_log`.
4. Flag missing required columns.
5. Continue ingestion where possible.
6. Fail only when minimum viable fields are absent.

### 14.4 Date Parsing

The date parser must handle:

- `MM/DD/YYYY`
- `DD/MM/YYYY`, flagged if ambiguous
- ISO dates
- Excel serial dates
- timestamp strings
- blank and invalid strings

Each parsed date should include:

- original raw value
- parsed date
- parser rule used
- parse confidence
- date issue flag

### 14.5 Ingestion Outputs

```text
data/lakehouse/bronze/
├── school_submissions/
├── enrollment_snapshots/
├── program_allocations/
├── school_masterlist/
├── file_manifest/
├── schema_drift_log/
└── ingestion_errors/
```

---

## 15. Data Quality Design

### 15.1 DQA Philosophy

The platform should not simply drop bad records. It should classify issues, preserve records where safe, and produce reviewable outputs.

Quality checks should be:

- explicit
- versioned
- testable
- explainable
- visible in dashboards
- linked to source files and source rows

### 15.2 Severity Levels

| Severity | Meaning | Example |
|---|---|---|
| CRITICAL | Cannot be used without correction | biologically impossible height |
| HIGH | Likely invalid, needs review | birthdate mismatch across periods |
| MEDIUM | Suspicious but usable with flag | age-grade mismatch |
| LOW | Minor formatting or metadata issue | unexpected capitalization |

### 15.3 DQA Rule Categories

#### Schema Checks

- required canonical columns mapped from each file
- unexpected and optional-missing columns retained in the bronze drift log

#### Completeness Checks

- missing learner reference number
- missing sex
- missing birthdate
- missing height
- missing weight

#### Range Checks

- height below plausible minimum
- height above plausible maximum
- weight below plausible minimum
- weight above plausible maximum
- malformed 12-digit learner reference number
- ambiguous, Excel-serial, timestamp-suffixed, or impossible dates

#### Consistency Checks

- birthdate differs across baseline and endline
- sex differs across baseline and endline
- endline height decreases beyond tolerance

#### Duplicate Checks

- exact duplicate row
- duplicate LRN within same school-period
- duplicate LRN with a name variant within school-period

#### Linkage Review Conditions

- no endline match
- multiple candidate matches
- low-confidence match
- school transfer detected
- conflicting deterministic and probabilistic match

#### Program Exposure Checks

- current enrollment exceeds allocation base
- source file submitted after its reporting window and grace period
- submitted school name drifts from the masterlist

#### Measurement Quality Checks

- suspicious rounding or heaping
- height decreases beyond tolerance

### 15.4 DQA Outputs

| Output | Description |
|---|---|
| `silver_dqa_issues` | Row-level issue registry |
| `gold_dqa_command_center` | Aggregated DQA metrics |
| `gold_dqa_scorecard` | Injected, detected, missed, false-positive, sensitivity, and precision metrics |
| `data_quality_report.html` | Human-readable report |
| `dqa_rules.md` | Documentation of checks |

---

## 16. Record Linkage Design

### 16.1 Goal

Link synthetic baseline and endline child records to create a child-level panel.

### 16.2 Matching Strategy

The linkage module uses a staged approach.

#### Stage 1: Deterministic Matching

Match records using high-confidence keys:

1. exact `lrn_clean` within school
2. exact school + standardized name + birthdate + sex
3. exact name + birthdate + sex across transferred school

#### Stage 2: Probabilistic Matching

Use Splink when deterministic rules are insufficient.

Candidate fields:

- standardized full name and first-letter blocking key
- sex
- birthdate
- school-scoped blocking

#### Stage 3: Review Queue

Records are sent to review if:

- match score is within gray zone
- multiple candidates exceed threshold
- deterministic and probabilistic decisions conflict
- birthdate differs but name and sex are close
- school transfer is detected

### 16.3 Linkage Outputs

| Output | Description |
|---|---|
| `silver_linkage_candidates` | Candidate pairs and scores |
| `silver_linkage_results` | Accepted links |
| `gold_linkage_review_mart` | Review queue and match quality metrics |
| `gold_linkage_scorecard` | Precision, recall, F1, match rate, review size, and transfer recall across thresholds |

### 16.4 Linkage Metrics

- baseline records
- endline records
- deterministic match rate
- probabilistic match rate
- unmatched baseline rate
- unmatched endline rate
- review queue size
- average match probability
- match rate by school
- match rate by grade
- match rate by treatment status

---

## 17. Transformation Design

### 17.1 Silver Transformations

Silver transformations will standardize records into canonical tables.

Examples:

- standardize column names
- parse dates
- normalize sex values
- normalize grade labels
- standardize school names
- compute age at measurement
- compute BMI
- attach school IDs
- attach source metadata
- attach DQA flags

### 17.2 Gold Transformations

Gold transformations create privacy-safe data products after DQA and linkage.

Examples:

- build baseline-endline child panel
- build school-level monitoring mart
- build DQA summary by school
- build program exposure mart
- build dashboard metrics
- build export files for analysts

### 17.3 Implemented dbt Model Layers

```text
dbt/models/
├── staging/
│   ├── stg_bronze_school_submissions.sql
│   ├── stg_bronze_enrollment.sql
│   ├── stg_bronze_allocations.sql
│   ├── stg_bronze_schools.sql
│   ├── stg_dqa_issues.sql
│   ├── stg_linkage_candidates.sql
│   └── stg_linkage_results.sql
├── silver/
│   ├── silver_child_records.sql
│   ├── silver_measurements.sql
│   ├── silver_schools.sql
│   └── silver_allocations.sql
└── gold/
    ├── gold_evaluation_child_panel.sql
    ├── gold_school_monitoring_mart.sql
    ├── gold_dqa_command_center.sql
    ├── gold_linkage_review_mart.sql
    ├── gold_program_exposure_mart.sql
    └── gold_public_dashboard_metrics.sql
```

### 17.4 Transformation Testing

The project defines 27 dbt schema, relationship, uniqueness, accepted-value, and reconciliation tests.

Examples:

- unique keys
- not-null keys
- accepted values
- relationship tests
- row-count reconciliation
- no duplicate child-period records
- no orphan school IDs
- no missing treatment status in gold evaluation panel

---

## 18. Orchestration Design

### 18.1 Implemented Orchestrator

The platform uses **Dagster** software-defined assets. The CLI and Dagster call the same Python entry points, avoiding a second orchestration-specific pipeline implementation.

### 18.2 Pipeline Assets

```text
synthetic_source_files
        ↓
bronze_layer
        ↓
silver_layer
   ↙           ↘
dqa_issue_registry   linkage_results
   ↘           ↙
      gold_layer
          ↓
 measured_scorecards
          ↓
   public_exports
```

Each asset records materialization metadata appropriate to its boundary, including profile/scale, files and rows processed, issue counts, linkage rows, and output stage results. The eight-asset graph is materialized end to end by an integration test.

### 18.3 Jobs

| Job | Description |
|---|---|
| `full_refresh_job` | Run full pipeline |
| `quality_job` | Generate, ingest, build silver, and run DQA |
| `reporting_job` | Build gold, scorecards, reports, and exports |

A weekly schedule targets `full_refresh_job`. Fine-grained local execution remains available through the CLI and Makefile.

### 18.4 Observability

Track:

- run ID
- start and end time
- task duration
- rows read
- rows written
- rows rejected
- files processed
- DQA issue counts
- match rates
- failed tasks
- retry counts

---

## 19. Observability and Monitoring

### 19.1 Operational Metrics

| Metric | Description |
|---|---|
| `files_discovered` | Number of source files found |
| `files_ingested` | Number of files successfully ingested |
| `files_failed` | Number of failed files |
| `rows_ingested` | Rows written to bronze |
| `rows_silver` | Rows written to silver |
| `rows_gold_panel` | Rows written to evaluation panel |
| `pipeline_duration_seconds` | Total run duration |
| `task_failure_count` | Number of failed tasks |

### 19.2 Data Quality Metrics

| Metric | Description |
|---|---|
| `critical_issues` | Count of critical issues |
| `high_issues` | Count of high issues |
| `missing_height_rate` | Missing height rate |
| `missing_weight_rate` | Missing weight rate |
| `invalid_date_rate` | Invalid date rate |
| `duplicate_rate` | Duplicate record rate |
| `outlier_rate` | Anthropometric outlier rate |

### 19.3 Linkage Metrics

| Metric | Description |
|---|---|
| `deterministic_match_rate` | Share matched deterministically |
| `probabilistic_match_rate` | Share matched probabilistically |
| `unmatched_baseline_rate` | Baseline records without endline match |
| `review_queue_rate` | Share requiring review |
| `median_match_score` | Median match probability |

### 19.4 Freshness Metrics

| Metric | Description |
|---|---|
| `latest_baseline_submission` | Latest baseline source file date |
| `latest_endline_submission` | Latest endline source file date |
| `stale_school_count` | Schools without recent expected submission |

---

## 20. Serving Layer

### 20.1 Data Quality Command Center

A Streamlit dashboard will serve as the main public-facing feature.

Pages:

1. **Overview**
   - schools processed
   - records processed
   - files ingested
   - pipeline status
   - key DQA issue counts

2. **School Submission Monitoring**
   - school file completeness
   - baseline and endline submission status
   - late or missing submissions

3. **Data Quality**
   - issue counts by severity
   - issue counts by school
   - issue counts by field
   - outlier distributions
   - missingness heatmap

4. **Record Linkage**
   - match rates
   - linkage confidence distribution
   - review queue
   - unmatched records

5. **Program Exposure**
   - allocation vs current enrollment
   - dilution ratio
   - effective ration estimate
   - treatment-control coverage

6. **Evaluation Readiness**
   - complete panel count
   - valid baseline and endline measurements
   - measurement timing distribution
   - export readiness checks

### 20.2 Analyst SQL Views

The platform should expose DuckDB SQL views:

```sql
select * from gold_evaluation_child_panel;
select * from gold_school_monitoring_mart;
select * from gold_dqa_command_center;
select * from gold_program_exposure_mart;
```

### 20.3 Export Files

```text
outputs/exports/
├── evaluation_child_panel.{csv,parquet}
├── school_monitoring_mart.{csv,parquet}
├── dqa_command_center.{csv,parquet}
├── linkage_review_mart.{csv,parquet}
├── program_exposure_mart.{csv,parquet}
├── public_dashboard_metrics.{csv,parquet}
└── data_dictionary.csv
```

The score command also materializes `gold_dqa_scorecard.parquet` and `gold_linkage_scorecard.parquet` inside the gold layer. Three generated HTML reports cover data quality, pipeline execution, and evaluation readiness.

### 20.4 Documentation Site

The committed documentation includes:

- system architecture
- data dictionary
- data contracts
- DQA rules
- lineage diagrams
- synthetic data disclaimer
- portfolio walkthrough

Operational and incident-response playbooks are production extensions, not public-demo v2.0 artifacts.

---

## 21. Security and Privacy Design

### 21.1 Privacy-by-Design Principles

1. Use synthetic data only.
2. Keep raw synthetic PII-like fields separate from gold outputs.
3. Hash synthetic learner IDs.
4. Do not export raw names in gold marts.
5. Include a PII scanner in CI.
6. Document what would be restricted in a real deployment.
7. Keep secrets out of the repository.
8. Use `.env.example` only.

### 21.2 Access Model for Real-World Deployment

Although the public project is local and synthetic, document a real-world access model.

| Role | Access |
|---|---|
| Data engineer | bronze, silver, gold, logs |
| M&E analyst | gold marts and documentation |
| Program manager | aggregated dashboard only |
| School reviewer | school-specific DQA queue |
| Public viewer | synthetic aggregate dashboard only |

### 21.3 Privacy Threat Model

Document risks and mitigations.

| Risk | Mitigation |
|---|---|
| accidental real data commit | PII scanner, synthetic-only policy |
| reidentification | no real names, no real IDs, no real addresses |
| sensitive small-cell reporting | suppress small cells in public dashboard |
| secrets leakage | `.env.example`, no credentials |
| raw PII exposure | raw names excluded from gold exports |

---

## 22. CI/CD Design

### 22.1 GitHub Actions Workflow

The implemented `.github/workflows/ci.yml` runs on pull requests, feature/main pushes, and manual dispatch with three jobs:

1. **Quality:** install with uv, Ruff lint/format, configuration doctor, and unit tests.
2. **Pipeline:** run the fixed-seed tiny full refresh, all integration/privacy/regression tests, scan for sensitive-looking content, and upload exports/reports.
3. **Container:** build the dashboard Docker image.

A separate nightly workflow is not included. Manual dispatch on the same workflow exercises the identical production path and avoids maintaining two divergent CI definitions.

### 22.2 Test Types

| Test type | Examples |
|---|---|
| Unit tests | date parser, schema mapper, DQA rules |
| Integration tests | ingestion to bronze, silver build, linkage run |
| Data tests | dbt uniqueness, not-null, relationships |
| Regression tests | row-count reconciliation and fixed-seed DQA/linkage metric floors |
| Smoke tests | full tiny pipeline and full Dagster asset graph |
| Privacy tests | no raw names in gold outputs |

---

## 23. Command Line Interface

The Typer CLI provides:

Example commands:

```bash
sbfp-platform generate-demo-data
sbfp-platform ingest
sbfp-platform build-silver
sbfp-platform run-dqa
sbfp-platform run-linkage
sbfp-platform build-gold
sbfp-platform score
sbfp-platform export
sbfp-platform full-refresh
sbfp-platform doctor
```

### 23.1 Example Local Workflow

```bash
uv sync --extra dev
sbfp-platform doctor --profile tiny
sbfp-platform full-refresh --profile tiny --seed 2026

streamlit run dashboards/streamlit_app.py
```

### 23.2 Makefile Commands

```makefile
install:
	uv sync --extra dev

generate:
	uv run sbfp-platform generate-demo-data

pipeline:
	uv run sbfp-platform full-refresh --profile $(PROFILE) --seed $(SEED)

test:
	uv run pytest

lint:
	uv run ruff check .

dashboard:
	uv run streamlit run dashboards/streamlit_app.py

dagster:
	uv run dagster dev -m orchestration.dagster_project.definitions

scan:
	uv run sbfp-platform-scan-pii

clean:
	rm -rf data/synthetic_raw data/ground_truth data/lakehouse outputs/exports outputs/reports dbt/target
```

---

## 24. Configuration Design

### 24.1 `project.yml`

```yaml
project_name: school-feeding-data-platform
environment: local
default_seed: 2026
default_profile: demo
max_workers: 4
```

### 24.2 `paths.yml`

```yaml
raw_data_dir: data/synthetic_raw
ground_truth_dir: data/ground_truth
lakehouse_dir: data/lakehouse
bronze_dir: data/lakehouse/bronze
silver_dir: data/lakehouse/silver
gold_dir: data/lakehouse/gold
linkage_dir: data/lakehouse/linkage
outputs_dir: outputs
```

### 24.3 `synthetic_data.yml`

```yaml
profiles:
  tiny: {divisions: 1, municipalities: 2, schools: 5, children: 1000}
  demo: {divisions: 3, municipalities: 20, schools: 40, children: 12000}
  large: {divisions: 3, municipalities: 20, schools: 150, children: 50000}
baseline_retention_rate: 0.88
treatment_share: 0.5
issue_rates:
  missing_lrn: 0.05
  date_format_ambiguity: 0.04
  duplicate_records: 0.02
  implausible_height: 0.005
  implausible_weight: 0.005
  school_name_drift: 0.03
```

### 24.4 `dqa_rules.yml`

```yaml
thresholds:
  height_cm: {min: 80, max: 200}
  weight_kg: {min: 10, max: 100}
  age_years: {min: 4, max: 15}
  measurement_elapsed_days: {min: 90, max: 300}
rules:
  - rule_id: DQA_RANGE_IMPLAUSIBLE_HEIGHT
    severity: CRITICAL
    scope: record
    detects: [implausible_height]
```

### 24.5 `linkage_rules.yml`

```yaml
deterministic:
  passes:
    - {pass_id: DET_EXACT_LRN, keys: [school_id, lrn_clean]}
    - {pass_id: DET_NAME_DOB_SEX, keys: [school_id, student_name_clean, birthday_str, sex]}
    - {pass_id: DET_NAME_DOB_SEX_CROSS_SCHOOL, keys: [student_name_clean, birthday_str, sex]}

probabilistic:
  backend: duckdb
  scope: global
  model_uid: measured_trust_splink_v1
  prediction_blocking_rules:
    - "l.lrn_clean = r.lrn_clean"
    - "l.student_name_clean = r.student_name_clean"
    - "l.birthday_str = r.birthday_str"
  em_training_rules:
    - "l.lrn_clean = r.lrn_clean"
    - "l.birthday_str = r.birthday_str AND l.sex = r.sex"
  comparisons:
    - {column: lrn_clean, method: exact}
    - {column: student_name_clean, method: jaro_winkler}
    - {column: birthday_str, method: date_of_birth}
    - {column: sex, method: exact}
    - {column: school_id, method: exact}
  accept_threshold: 0.10
  review_floor: 0.10
  sweep: [0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.90]
```

---

## 25. Documentation Requirements

### 25.1 README

The implemented README includes:

1. project overview
2. architecture diagram
3. what skills the project demonstrates
4. quickstart
5. sample outputs
6. verified tiny-profile metrics
7. privacy statement and honest limitations
8. repository map
9. CLI, Makefile, Dagster, and Docker commands

A screenshot was deliberately not fabricated when the in-app browser was unavailable. Streamlit AppTest provides executable coverage for all six dashboard views; a real screenshot remains a non-blocking publication enhancement.

### 25.2 Architecture Document

`docs/architecture.md` should include:

- lifecycle mapping
- bronze-silver-gold architecture
- storage design
- orchestration design
- data contracts
- trade-offs
- local-first rationale

### 25.3 Data Dictionary

`docs/data_dictionary.md` should describe:

- raw fields
- canonical fields
- gold mart fields
- data types
- allowed values
- issue flags

### 25.4 Data Contracts

`docs/data_contracts.md` should define:

- required source fields
- optional source fields
- accepted formats
- schema versions
- breaking vs nonbreaking changes

### 25.5 DQA Rules

`docs/dqa_rules.md` should document:

- rule name
- description
- fields checked
- severity
- rationale
- suggested action

### 25.6 Privacy and Synthetic Data

`docs/privacy_and_synthetic_data.md` should include:

- synthetic data disclaimer
- PII handling
- what is excluded
- privacy threat model
- real-world deployment restrictions

### 25.7 Architecture Decision Records

Six ADRs record the major choices.

Minimum ADRs:

1. Local DuckDB and Parquet lakehouse
2. Ground-truth isolation boundary
3. Dagster for cross-framework orchestration
4. dbt ownership of set-based transformations
5. Bronze-silver-gold boundaries
6. Code-only synthetic release

---

## 26. As-Built Milestone Record

| Phase | Implemented evidence | Status |
|---|---|---|
| 0 — Setup | uv package, frozen contracts/config, CLI, Makefile, CI | Complete |
| 1 — Generator | deterministic raw CSV/XLSX, truth tables, 20 defect classes | Complete |
| 2 — Bronze | manifest/history, hash idempotency, drift/error logs, Parquet | Complete |
| 3 — DQA | 21 configured rules, issue registry, measured scorecard | Complete |
| 4 — Transformations | four silver and six gold dbt models with 27 data tests | Complete |
| 5 — Linkage | exact-rule benchmark, globally trained/persisted Splink, one-to-one resolver, review queue | Complete |
| 6 — Orchestration | eight Dagster assets, three jobs, weekly schedule, materialization test | Complete |
| 7 — Serving | six Streamlit pages, dual-format exports, three HTML reports | Complete |
| 8 — Delivery | GitHub Actions quality/pipeline/container jobs, Docker/Compose, privacy scanner | Complete; remote CI validates Docker |
| 9 — Portfolio | README, data/architecture/privacy documentation, six ADRs, walkthrough | Complete; screenshot deferred |

The detailed phase definitions below are retained as the original acceptance contract. Implemented module boundaries were consolidated where doing so reduced ceremony without changing behavior.

### Phase 0: Project Setup

Deliverables:

- repository initialized
- `pyproject.toml`
- `src/` package structure
- Makefile
- ruff and pytest configured
- CI skeleton
- README draft

Acceptance criteria:

- `uv sync` works
- `pytest` runs
- `ruff check .` runs
- GitHub Actions passes

### Phase 1: Synthetic Data Generator

Deliverables:

- school generator
- child generator
- measurement generator
- allocation generator
- issue injection
- raw Excel and CSV writer

Acceptance criteria:

- creates realistic source folders
- generates deterministic output by seed
- produces known quality issues
- includes synthetic data disclaimer

### Phase 2: Bronze Ingestion

Deliverables:

- file discovery
- file manifest
- Excel reader
- schema alias mapper
- date parser
- bronze writer
- ingestion error log

Acceptance criteria:

- ingests all generated files
- skips already ingested files by hash
- logs schema drift
- writes bronze Parquet files

### Phase 3: DQA Engine

Deliverables:

- schema checks
- completeness checks
- range checks
- consistency checks
- duplicate checks
- issue registry
- DQA summary tables

Acceptance criteria:

- detects injected issues
- classifies severity
- produces review queue
- produces DQA report data

### Phase 4: Silver and Gold Transformations

Deliverables:

- silver standardized tables
- gold evaluation panel
- school monitoring mart
- DQA command center mart
- program exposure mart
- export files

Acceptance criteria:

- gold panel has one row per linked child
- all gold outputs pass tests
- no raw names in gold exports
- row-count reconciliation is documented

### Phase 5: Record Linkage

Deliverables:

- deterministic matching
- probabilistic matching
- linkage thresholds
- review queue
- linkage metrics

Acceptance criteria:

- match rate is reported
- ambiguous matches are queued
- no duplicate accepted links
- linkage report is generated

### Phase 6: Orchestration

Deliverables:

- Dagster project
- assets
- jobs
- schedules
- materialization metadata
- run logs

Acceptance criteria:

- full pipeline can run from orchestrator
- asset graph shows dependencies
- failed steps produce readable logs
- metrics are captured

### Phase 7: Serving Layer

Deliverables:

- Streamlit dashboard
- HTML DQA report
- pipeline run summary
- evaluation readiness report
- Streamlit AppTest coverage for all six dashboard views

Acceptance criteria:

- dashboard runs locally
- all pages load
- metrics match gold tables
- executable dashboard test reports no exceptions

### Phase 8: CI/CD and Docker

Deliverables:

- GitHub Actions
- Dockerfile
- docker-compose
- tiny-profile pipeline and container jobs in `ci.yml`
- PII scanner

Acceptance criteria:

- CI passes on push
- Docker build succeeds
- fixed-seed tiny full refresh runs in CI
- privacy checks pass

### Phase 9: Documentation and Portfolio Polish

Deliverables:

- polished README
- architecture diagrams
- data dictionary
- ADRs
- walkthrough
- verified metrics and generated sample-output workflow

Acceptance criteria:

- reviewer can understand the project in under 5 minutes
- reviewer can run demo in under 15 minutes
- README clearly maps project to data engineering skills

---

## 27. Acceptance Criteria for the Full Project

All criteria below are met by the implementation, subject to the remote-CI verification note after publication:

1. A user can clone the repo and run the full demo locally.
2. Synthetic raw files are generated from configuration.
3. Bronze, silver, and gold layers are created.
4. DQA issues are detected and summarized.
5. Baseline and endline records are linked.
6. A gold evaluation panel is exported.
7. A school monitoring mart is exported.
8. A Streamlit dashboard displays pipeline and DQA metrics.
9. Tests and CI pass.
10. Documentation explains architecture, data contracts, DQA rules, lineage, and privacy.
11. No real or sensitive data are included.
12. The README clearly showcases data engineering lifecycle skills.

Verification evidence: the fixed-seed tiny CLI refresh and full Dagster asset materialization both succeed; dbt reports 22 passing silver build nodes and 15 passing gold build nodes; 407 pytest tests pass; Ruff, privacy, runtime gold/export privacy, and fixed-seed score regression checks pass. Docker cannot be executed on the development host because the Docker CLI is absent, so the CI container job is the authoritative build check after branch publication.

---

## 28. Suggested Portfolio README Positioning

Use this language in the README:

> This project is a privacy-safe public-sector data engineering platform for school feeding monitoring and evaluation. It simulates messy school submissions and transforms them into trusted data products through a local lakehouse architecture, orchestrated ingestion, data quality checks, probabilistic record linkage, tested transformations, and dashboard-ready marts. The dataset is fully synthetic and does not contain real learner records.

---

## 29. Suggested LinkedIn or Portfolio Description

> I built a synthetic public-sector data platform that models the data engineering challenges of a school feeding evaluation: messy school Excel files, baseline-endline child measurements, data quality issues, program allocation mismatch, and record linkage. The platform uses Python, DuckDB, Parquet, Dagster, dbt, Pandera, Splink, Streamlit, pytest, Docker, and GitHub Actions to demonstrate an end-to-end data engineering lifecycle from source generation to analytics-ready serving.

---

## 30. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Project becomes too large | Build in phases, publish MVP first |
| Too many tools obscure the story | Keep README focused on lifecycle and outputs |
| Synthetic data looks unrealistic | Inject realistic school, date, measurement, and linkage issues |
| Dashboard becomes chart-heavy | Focus on operational command center metrics |
| Linkage module becomes complex | Start deterministic, add Splink later |
| dbt adds overhead | Use DuckDB SQL first, add dbt in Phase 4 |
| Orchestration delays MVP | Build CLI first, orchestrate after core pipeline |
| Privacy concerns | synthetic-only policy and PII scanner |

---

## 31. Initial MVP Scope and Implemented v2 Expansion

The following was the original minimum cut used to sequence delivery, not the final public scope.

The MVP should include only the following:

1. Synthetic data generator
2. Bronze ingestion
3. DQA checks
4. Silver standardized tables
5. Simple deterministic linkage
6. Gold evaluation panel
7. DQA command center table
8. Streamlit dashboard overview
9. Basic tests
10. README

MVP excludes:

- dbt
- Splink
- Docker
- full Dagster orchestration
- CI artifact upload
- advanced reports

This keeps the first version achievable while preserving the path to a stronger platform.

Version 2.0 implements every item originally deferred: dbt, Splink, Docker, full Dagster orchestration, CI artifact upload, and HTML reports. The only deferred portfolio artifact is a real dashboard screenshot; all six views are covered by Streamlit AppTest.

---

## 32. Build History

The implementation landed in the following independently verified order:

1. Create repo and package skeleton.
2. Build synthetic data generator.
3. Build ingestion and file manifest.
4. Build DQA issue registry.
5. Build silver tables.
6. Build deterministic linkage.
7. Build gold evaluation panel.
8. Build the six-view dashboard, HTML reports, and privacy-safe exports.
9. Add Dagster orchestration, Docker/Compose, CI gates, regression floors, and portfolio documentation.

---

## 33. Definition of Done by Skill Area

| Skill area | Definition of done |
|---|---|
| Python engineering | modular package, CLI, tests, type-aware code |
| SQL and modeling | silver and gold models, documented fields, tests |
| Data architecture | bronze-silver-gold lakehouse, ADRs, diagrams |
| Data quality | issue registry, severity, dashboards, rule docs |
| Orchestration | eight-asset graph, three jobs, schedule, readable Dagster/CLI logs |
| Observability | materialization metadata, file/row/issue/linkage counts, run IDs |
| Privacy | synthetic data, PII scanner, no raw names in gold |
| Serving | dashboard, reports, exports, SQL views |
| CI/CD | GitHub Actions, linting, tests, sample run |
| Communication | README, walkthrough, executable dashboard test, architecture docs |

---

## 34. Future Extensions

After the main version, possible extensions include:

1. Cloud deployment on GCP, AWS, or Azure.
2. Object storage using S3-compatible MinIO.
3. OpenLineage integration.
4. Data catalog using DataHub or OpenMetadata.
5. Great Expectations data docs.
6. Evidence-ready Quarto report generation.
7. Small-cell suppression for public dashboards.
8. Stream processing simulation for late submissions.
9. API serving layer using FastAPI.
10. dbt semantic layer or metrics layer.

---

## 35. Final Recommendation

The project is built and presented as a **public-sector data platform**, not a data cleaning script.

The strongest portfolio message is:

> This project shows how to engineer trust in messy administrative data.

The technical story is:

> Raw school submissions are generated, stored, ingested, validated, linked, transformed, monitored, and served as trusted data products.

That is the right level of ambition for showcasing data engineering skill while staying grounded in the school feeding evaluation domain.
