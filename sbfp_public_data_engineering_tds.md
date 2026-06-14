# Technical Design Specification: Public School Feeding Data Engineering Demo

**Project name:** `school-feeding-data-engineering-demo`  
**Working subtitle:** A privacy-safe data engineering portfolio project inspired by school-based feeding monitoring and evaluation workflows  
**Document type:** Technical Design Specification  
**Target audience:** Data engineers, analytics engineers, M&E specialists, public-sector data governance reviewers, and impact evaluation analysts  
**Status:** Draft for implementation  
**Last updated:** 2026-06-14  

---

## 1. Executive Summary

This project will build a public, privacy-safe data engineering showcase inspired by a School-Based Feeding Program (SBFP) monitoring and evaluation workflow. The public repository will not contain any confidential learner, school, or household records. Instead, it will use synthetic data that mimics the structure, quality issues, and workflow challenges of real school feeding administrative data.

The central product is an end-to-end reproducible pipeline that transforms raw school-level baseline and endline files into an analysis-ready child panel. The pipeline will demonstrate ingestion, schema harmonization, date parsing, data quality assurance, probabilistic record linkage, panel construction, reporting, and optional dashboarding.

The project should be presented as a data engineering and evaluation-readiness system, not as a causal impact analysis. The public value is that it shows how messy school monitoring data can be made reliable enough for later evaluation, planning, and reporting.

---

## 2. Expert Roles Represented in the Design

This TDS is written from the combined perspective of the following subject matter experts:

| Role | Main contribution to the design |
|---|---|
| Data engineer | Pipeline orchestration, file ingestion, schema management, data validation, reproducible outputs |
| Analytics engineer | Warehouse modeling, staging tables, marts, documentation, metric definitions |
| M&E data systems specialist | Evaluation-readiness, indicator tracking, auditability, data quality workflows |
| Impact evaluation analyst | Treatment assignment structure, panel construction, baseline-endline consistency, clustering considerations |
| Public-sector data governance reviewer | Privacy, synthetic data, safe public release, reproducibility without exposing confidential records |
| Nutrition program data reviewer | Anthropometric plausibility, measurement timing, height and weight quality checks |

---

## 3. Project Objectives

### 3.1 Primary Objective

Build a public portfolio-grade data engineering project that demonstrates how school-level feeding program records can be converted into a validated, linked, analysis-ready child panel using a fully synthetic dataset.

### 3.2 Secondary Objectives

1. Demonstrate robust ingestion of messy multi-file school records.
2. Implement a data quality assurance engine for child, school, and wave-level records.
3. Implement probabilistic baseline-to-endline record linkage.
4. Produce clean panel outputs for downstream analysis.
5. Produce human-readable data quality and linkage reports.
6. Provide a public documentation site or README that explains the system clearly.
7. Keep the project privacy-safe, reproducible, and easy for hiring reviewers to run.

### 3.3 Non-Objectives

This public demo will not:

1. Publish confidential student records.
2. Publish actual school names if disclosure is restricted.
3. Reproduce official impact estimates.
4. Claim to represent official SBFP results.
5. Present synthetic results as real program evidence.
6. Build a full production government data system.
7. Use the public synthetic data for policy inference.

---

## 4. Recommended Public Positioning

Use this as the repository description:

> A privacy-safe data engineering demo that transforms synthetic school feeding monitoring records into an analysis-ready child panel through reproducible ingestion, validation, probabilistic record linkage, and data quality reporting.

Use this as the README opening paragraph:

> This repository demonstrates how school-based feeding monitoring records can be engineered into evaluation-ready data. The project uses fully synthetic data that mimic common administrative data challenges: inconsistent school files, date-format errors, missing anthropometric measurements, duplicate learner records, baseline-to-endline linkage uncertainty, and school-level treatment assignment. No confidential learner or school records are included.

---

## 5. Repository Name and Branding

### 5.1 Recommended Repository Name

```text
school-feeding-data-engineering-demo
```

### 5.2 Alternative Names

```text
sbfp-synthetic-data-pipeline
school-feeding-evaluation-data-pipeline
admin-data-pipeline-school-feeding
```

### 5.3 Recommended Tagline

```text
From raw school records to evaluation-ready child panels.
```

---

## 6. High-Level System Architecture

```text
Synthetic raw files
        |
        v
Ingestion and schema standardization
        |
        v
Data quality validation
        |
        v
Cleaned baseline and endline records
        |
        v
Probabilistic baseline-to-endline linkage
        |
        v
Linked child panel
        |
        v
Evaluation-ready analytical tables
        |
        v
Data quality reports, linkage reports, dashboard
```

### 6.1 Core Components

| Component | Purpose |
|---|---|
| Synthetic data generator | Creates fake but realistic school, child, household, and measurement records |
| Ingestion layer | Reads raw CSV or Excel files from school folders |
| Standardization layer | Maps messy columns into canonical field names and types |
| Data quality engine | Flags missingness, invalid dates, implausible values, duplicates, and inconsistencies |
| Linkage engine | Links baseline and endline child records probabilistically |
| Panel builder | Creates a child-level panel with baseline and endline outcomes |
| Reporting layer | Produces HTML or Markdown reports for DQA and linkage review |
| Optional dashboard | Provides visual summaries of processing status and data quality |

---

## 7. Recommended Technology Stack

### 7.1 Core Stack

| Layer | Tool | Rationale |
|---|---|---|
| Language | Python 3.11+ | Strong data engineering and testing ecosystem |
| Package management | `uv` | Fast and reproducible environment setup |
| Data frames | `pandas`, `polars` optional | Familiar and suitable for medium data |
| Local warehouse | `duckdb` | Fast local analytical database |
| File formats | CSV, Parquet, Excel | Mirrors common government workflows |
| Validation | `pandera` or custom validators | Schema and data quality validation |
| Record linkage | `splink` | Probabilistic linkage with DuckDB backend |
| Reporting | Quarto, Markdown, or Jinja templates | Easy static outputs |
| Dashboard | Streamlit optional | Quick interactive public demo |
| Testing | `pytest` | Unit and integration tests |
| CI | GitHub Actions | Public reproducibility and quality signal |

### 7.2 Optional Analytics Engineering Stack

| Layer | Tool | When to add |
|---|---|---|
| Transformations | `dbt-duckdb` | Add after MVP is stable |
| Data docs | dbt docs | Good portfolio enhancement |
| Data contracts | `pandera` or dbt tests | Add for maturity |
| Containerization | Docker | Add once workflow is stable |
| Orchestration | Makefile first, Dagster later | Avoid Airflow for MVP |

### 7.3 R Stack for Optional Analysis Checks

If an R analysis demo is added later, follow this convention:

```r
if (!requireNamespace("pacman", quietly = TRUE)) install.packages("pacman")
pacman::p_load(dplyr, ggplot2, fixest, here, readr)
```

R should only be used for optional analysis examples. The core public data engineering project should stay Python-first.

---

## 8. Proposed Repository Structure

```text
school-feeding-data-engineering-demo/
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── Makefile
├── .gitignore
├── .python-version
├── .github/
│   └── workflows/
│       └── ci.yml
├── config/
│   ├── project.yml
│   ├── schema_child.yml
│   ├── schema_school.yml
│   ├── dqa_rules.yml
│   └── linkage.yml
├── data/
│   ├── synthetic_raw/
│   │   ├── baseline/
│   │   └── endline/
│   ├── synthetic_reference/
│   │   ├── school_master.csv
│   │   ├── barangay_master.csv
│   │   └── treatment_assignment.csv
│   ├── interim/
│   ├── processed/
│   └── outputs/
├── src/
│   └── school_feeding_pipeline/
│       ├── __init__.py
│       ├── cli.py
│       ├── synthetic/
│       │   ├── generate_school_master.py
│       │   ├── generate_child_records.py
│       │   ├── inject_quality_issues.py
│       │   └── write_raw_school_files.py
│       ├── ingest/
│       │   ├── discover_files.py
│       │   ├── read_school_file.py
│       │   ├── standardize_columns.py
│       │   └── parse_dates.py
│       ├── validate/
│       │   ├── base.py
│       │   ├── schema.py
│       │   ├── completeness.py
│       │   ├── ranges.py
│       │   ├── consistency.py
│       │   ├── duplicates.py
│       │   ├── age_grade.py
│       │   └── linkage_quality.py
│       ├── linkage/
│       │   ├── prepare_linkage_inputs.py
│       │   ├── splink_model.py
│       │   ├── classify_matches.py
│       │   └── clerical_review_queue.py
│       ├── panel/
│       │   ├── build_child_panel.py
│       │   ├── build_school_panel.py
│       │   └── build_analysis_marts.py
│       ├── reporting/
│       │   ├── dqa_report.py
│       │   ├── linkage_report.py
│       │   ├── templates/
│       │   └── charts.py
│       └── utils/
│           ├── logging.py
│           ├── paths.py
│           └── privacy.py
├── notebooks/
│   ├── 01_explore_synthetic_raw_data.ipynb
│   └── 02_review_linkage_outputs.ipynb
├── reports/
│   ├── dqa_summary.md
│   ├── linkage_summary.md
│   └── evaluation_readiness_summary.md
├── dashboards/
│   └── streamlit_app.py
├── tests/
│   ├── test_synthetic_generation.py
│   ├── test_ingestion.py
│   ├── test_date_parsing.py
│   ├── test_dqa_rules.py
│   ├── test_linkage.py
│   └── test_panel_builder.py
└── docs/
    ├── technical_design_spec.md
    ├── data_dictionary.md
    ├── data_quality_rules.md
    ├── linkage_methodology.md
    ├── privacy_and_synthetic_data.md
    ├── portfolio_walkthrough.md
    └── future_work.md
```

---

## 9. Data Scope

### 9.1 Synthetic Entities

| Entity | Description |
|---|---|
| Division | Administrative education division |
| Municipality | Local government unit |
| Barangay | Small-area geographic unit |
| School | Unit of treatment assignment and reporting |
| Child | Unit of measurement and panel linkage |
| Household | Optional synthetic grouping of siblings |
| Baseline measurement | Pre-intervention anthropometric record |
| Endline measurement | Post-intervention anthropometric record |
| DQA issue | Row-level or school-level data quality issue |
| Linkage pair | Candidate baseline-endline pair |
| Panel record | Linked child-level baseline-endline record |

### 9.2 Synthetic Data Scale

Use a modest but realistic public scale:

| Scale parameter | MVP value | Stretch value |
|---|---:|---:|
| Divisions | 3 | 7 |
| Municipalities | 12 | 30 |
| Schools | 120 | 500 |
| Children per school | 80 to 350 | 50 to 900 |
| Total child baseline records | 20,000 | 150,000 |
| Total child endline records | 18,000 to 22,000 | 130,000 to 170,000 |
| Waves | 2 | 3 or more |
| Raw files | 240 | 1,000+ |

### 9.3 Data Privacy Rule

All public data must be synthetic. The data generator should not sample from real learner names, real LRNs, real addresses, real contact numbers, or exact school identifiers from confidential sources.

Synthetic data may mimic:

1. Field names.
2. File structure.
3. Error types.
4. Missingness patterns.
5. Record linkage uncertainty.
6. School-level treatment assignment.
7. Baseline-endline measurement timing.

Synthetic data must not mimic:

1. Actual learner identities.
2. Actual household addresses.
3. Actual phone numbers.
4. Real rare combinations that could identify a child or school.
5. Confidential operational records.

---

## 10. Canonical Data Model

### 10.1 Child Record Schema

| Field | Type | Required | Description |
|---|---|---:|---|
| `source_file` | string | Yes | Raw file where record came from |
| `wave` | string | Yes | `baseline` or `endline` |
| `division_code` | string | Yes | Synthetic division code |
| `municipality_code` | string | Yes | Synthetic municipality code |
| `school_id` | string | Yes | Synthetic school ID |
| `school_name_raw` | string | Yes | Raw school name as it appeared in file |
| `child_record_id` | string | Yes | Internal row-level record ID |
| `lrn_raw` | string | No | Synthetic learner reference number, may be missing |
| `child_name_raw` | string | Yes | Synthetic raw name |
| `child_name_std` | string | Yes | Standardized name |
| `sex` | string | Yes | `Male`, `Female`, or missing |
| `grade` | string | Yes | Kinder to Grade 6 |
| `section` | string | No | Raw section name |
| `date_of_birth_raw` | string | Yes | Raw date as entered |
| `date_of_birth` | date | No | Parsed date |
| `measurement_date_raw` | string | Yes | Raw date as entered |
| `measurement_date` | date | No | Parsed date |
| `age_years_reported` | float | No | Reported age |
| `age_years_computed` | float | No | Computed age at measurement |
| `weight_kg` | float | No | Weight in kilograms |
| `height_cm` | float | No | Height in centimeters |
| `bmi` | float | No | Computed BMI |
| `bfaz` | float | No | Synthetic BMI-for-age z-score |
| `hfaz` | float | No | Synthetic height-for-age z-score |
| `is_4ps` | boolean | No | Synthetic social protection indicator |
| `is_ip` | boolean | No | Synthetic IP indicator, optional |
| `dewormed` | boolean | No | Synthetic deworming indicator |
| `created_at` | datetime | Yes | Pipeline creation timestamp |

### 10.2 School Master Schema

| Field | Type | Required | Description |
|---|---|---:|---|
| `school_id` | string | Yes | Synthetic school ID |
| `school_name` | string | Yes | Synthetic school name |
| `division_code` | string | Yes | Synthetic division |
| `municipality_code` | string | Yes | Synthetic municipality |
| `barangay_code` | string | Yes | Synthetic barangay |
| `urban_rural` | string | Yes | Urban or rural |
| `treated` | boolean | Yes | School-level treatment assignment |
| `matched_pair_id` | string | No | Synthetic matched pair |
| `has_school_nurse` | boolean | No | School resource indicator |
| `has_standard_scale` | boolean | No | Measurement resource indicator |
| `has_height_board` | boolean | No | Measurement resource indicator |
| `has_safe_water` | boolean | No | WASH indicator |
| `has_handwashing_facility` | boolean | No | WASH indicator |
| `allocation_base_enrollment` | integer | No | Synthetic allocation base |
| `current_enrollment` | integer | No | Synthetic current enrollment |

### 10.3 Linkage Output Schema

| Field | Type | Required | Description |
|---|---|---:|---|
| `baseline_record_id` | string | Yes | Baseline record ID |
| `endline_record_id` | string | Yes | Endline record ID |
| `school_id` | string | Yes | School ID |
| `match_probability` | float | Yes | Probability from linkage model |
| `match_status` | string | Yes | `auto_match`, `review`, `non_match` |
| `blocking_rule` | string | No | Blocking rule that generated pair |
| `name_similarity` | float | No | Name similarity score |
| `dob_match_level` | string | No | Exact, month-year, year-only, mismatch |
| `sex_match` | boolean | No | Whether sex agrees |
| `grade_distance` | integer | No | Difference in grade level |

### 10.4 Analysis-Ready Panel Schema

| Field | Type | Required | Description |
|---|---|---:|---|
| `panel_id` | string | Yes | Stable synthetic child panel ID |
| `school_id` | string | Yes | School ID |
| `treated` | boolean | Yes | School-level treatment assignment |
| `division_code` | string | Yes | Division |
| `municipality_code` | string | Yes | Municipality |
| `grade_baseline` | string | Yes | Baseline grade |
| `grade_endline` | string | No | Endline grade |
| `sex` | string | Yes | Child sex |
| `age_baseline` | float | Yes | Computed baseline age |
| `age_endline` | float | No | Computed endline age |
| `weight_kg_baseline` | float | No | Baseline weight |
| `weight_kg_endline` | float | No | Endline weight |
| `height_cm_baseline` | float | No | Baseline height |
| `height_cm_endline` | float | No | Endline height |
| `bfaz_baseline` | float | No | Baseline BFAZ |
| `bfaz_endline` | float | No | Endline BFAZ |
| `hfaz_baseline` | float | No | Baseline HFAZ |
| `hfaz_endline` | float | No | Endline HFAZ |
| `measurement_gap_days` | integer | No | Endline minus baseline measurement date |
| `match_probability` | float | Yes | Final linkage confidence |
| `dqa_issue_count` | integer | Yes | Number of record-level DQA flags |
| `panel_inclusion_flag` | boolean | Yes | Whether record is usable for analysis demo |

---

## 11. Synthetic Data Generation Design

### 11.1 Purpose

The synthetic generator should create a dataset that is realistic enough to demonstrate data engineering challenges while remaining completely safe for public release.

### 11.2 Synthetic Data Generation Steps

1. Generate synthetic administrative geography.
2. Generate synthetic schools.
3. Assign treatment at the school level.
4. Generate baseline children.
5. Generate endline children.
6. Simulate attrition, transfer-in, and duplicate records.
7. Generate height and weight values.
8. Generate BFAZ and HFAZ-like synthetic z-scores.
9. Inject data quality issues.
10. Write raw school files with inconsistent formats.

### 11.3 Treatment Assignment Logic

Treatment is assigned at school level, not child level.

```text
school_id, treated
SCH0001, true
SCH0002, false
SCH0003, true
```

All children in a treatment school inherit treatment status. This preserves the logic needed for evaluation-readiness without estimating actual program effects.

### 11.4 Data Quality Issues to Inject

| Issue type | Example | Target rate |
|---|---|---:|
| Missing LRN | blank learner ID | 10 percent |
| Missing measurement date | blank endline date | 3 percent |
| Date format flip | `05/10/2024` ambiguous | 5 percent |
| Excel serial date | `45291` instead of date string | 3 percent |
| Implausible height | 240 cm | 0.1 percent |
| Implausible weight | 4 kg or 150 kg | 0.2 percent |
| Duplicate child | Same child entered twice | 1 percent |
| Name typo | `Aisha` vs `Aisa` | 8 percent |
| Sex inconsistency | Male baseline, Female endline | 0.5 percent |
| Grade jump | Grade 1 to Grade 5 | 0.5 percent |
| School name variation | `Central ES` vs `Cent. Elem School` | 10 percent |
| Late measurement | Endline much later than expected | 5 percent |
| Allocation mismatch | Current enrollment exceeds allocation base | 40 percent |

### 11.5 Example CLI

```bash
uv run school-feeding generate-synthetic \
  --schools 120 \
  --children-min 80 \
  --children-max 350 \
  --seed 20260614
```

Expected outputs:

```text
data/synthetic_raw/baseline/
data/synthetic_raw/endline/
data/synthetic_reference/school_master.csv
data/synthetic_reference/treatment_assignment.csv
```

---

## 12. Ingestion Design

### 12.1 Purpose

The ingestion layer reads raw school files from nested folders and converts them into standardized baseline and endline tables.

### 12.2 Supported Input Formats

| Format | MVP support | Notes |
|---|---:|---|
| CSV | Yes | Easier for public demo |
| XLSX | Yes | Important for realism |
| XLS | Optional | Add only if needed |
| Google Sheets | No | Out of scope |

### 12.3 Ingestion Rules

1. Recursively scan the raw baseline and endline directories.
2. Extract school metadata from folder path and file name.
3. Read each file with robust error handling.
4. Standardize columns using a configurable alias map.
5. Preserve raw values before parsing.
6. Add `source_file`, `ingested_at`, and `row_number`.
7. Write standardized interim tables to Parquet.

### 12.4 Example Column Alias Map

```yaml
child_name:
  - Name
  - Learner Name
  - Student Name
  - Full Name

sex:
  - Sex
  - Gender

date_of_birth:
  - Date of Birth
  - DOB
  - BIRTH_DATE
  - Date of Birth (MM/DD/YY)

measurement_date:
  - Date of Weighing/Measuring
  - Date Measured
  - Weighing Date

weight_kg:
  - Weight
  - Weight (kg)
  - WT

height_cm:
  - Height
  - Height (cm)
  - HT
```

### 12.5 Example CLI

```bash
uv run school-feeding ingest \
  --raw-dir data/synthetic_raw \
  --out-dir data/interim
```

Expected outputs:

```text
data/interim/baseline_standardized.parquet
data/interim/endline_standardized.parquet
data/interim/ingestion_log.csv
```

---

## 13. Date Parsing Design

### 13.1 Purpose

Date parsing is a central feature because school records commonly contain mixed date formats.

### 13.2 Supported Date Formats

| Input type | Example | Handling |
|---|---|---|
| ISO date | `2024-08-15` | Direct parse |
| US style | `08/15/2024` | Parse as month-day-year |
| Ambiguous | `05/10/2024` | Flag for review if ambiguous |
| Excel serial | `45291` | Convert using Excel date origin |
| Timestamp string | `2024-08-15 00:00:00` | Extract date |
| Invalid date | `13/40/2024` | Set parsed value missing and flag |
| Blank | empty | Set missing and flag if required |

### 13.3 Date Issue Fields

| Field | Description |
|---|---|
| `date_parse_status` | `parsed`, `ambiguous`, `invalid`, `missing` |
| `date_parse_method` | `iso`, `mdy`, `excel_serial`, `timestamp`, `manual_flag` |
| `date_parse_warning` | Human-readable issue |
| `date_requires_review` | Boolean |

---

## 14. Data Quality Assurance Design

### 14.1 Validator Interface

Each validator should accept a dataframe and return a dataframe of issues.

```python
from dataclasses import dataclass
import pandas as pd

@dataclass
class DQAIssue:
    issue_id: str
    severity: str
    entity_level: str
    record_id: str | None
    school_id: str | None
    field_name: str | None
    issue_type: str
    message: str

class BaseValidator:
    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError
```

### 14.2 Severity Levels

| Severity | Meaning | Example |
|---|---|---|
| Critical | Prevents safe use of record | Impossible height or missing school ID |
| High | Needs review before analysis | Invalid measurement date |
| Medium | Potential issue | Age-grade mismatch |
| Low | Minor standardization concern | Unusual section label |

### 14.3 Validators

#### 14.3.1 Schema Validator

Checks that required columns exist and have compatible types.

Required checks:

1. `school_id` exists.
2. `wave` exists.
3. `child_name_raw` exists.
4. `sex` exists.
5. `grade` exists.
6. At least one of `lrn_raw` or `child_name_raw` exists.
7. Measurement fields are numeric or parseable.

#### 14.3.2 Completeness Validator

Computes missingness by field, wave, school, and division.

Example issue:

```text
HIGH: school SCH0023 has 35 percent missing endline measurement dates.
```

#### 14.3.3 Range Validator

Checks plausible values.

| Field | Rule |
|---|---|
| `weight_kg` | 10 to 100 kg, flag outside |
| `height_cm` | 70 to 200 cm, flag outside |
| `bmi` | 8 to 40, flag outside |
| `age_years_computed` | 4 to 15, flag outside |
| `bfaz` | -6 to 6, flag outside |
| `hfaz` | -6 to 6, flag outside |

#### 14.3.4 Consistency Validator

Checks cross-field consistency.

Rules:

1. Reported age should be close to computed age.
2. Endline age should be greater than baseline age.
3. Height should not decline materially unless measurement error is suspected.
4. Sex should not change across waves for high-confidence matches.
5. Date of birth should not change across waves for high-confidence matches.

#### 14.3.5 Duplicate Validator

Flags likely duplicate records within the same school and wave.

Blocking candidates:

1. Same LRN.
2. Same standardized name and date of birth.
3. Same standardized name and sex and grade.
4. Near-same name and same date of birth.

#### 14.3.6 Age-Grade Validator

Flags unlikely age-grade combinations.

| Grade | Expected age range |
|---|---|
| Kinder | 4 to 7 |
| Grade 1 | 5 to 9 |
| Grade 2 | 6 to 10 |
| Grade 3 | 7 to 11 |
| Grade 4 | 8 to 12 |
| Grade 5 | 9 to 13 |
| Grade 6 | 10 to 15 |

#### 14.3.7 Measurement Timing Validator

Flags suspicious timing.

Rules:

1. Baseline measurement should occur near school-year start.
2. Endline measurement should occur after baseline.
3. Baseline-to-endline gap should fall within expected range.
4. School-level measurement windows should be summarized.

#### 14.3.8 Linkage Quality Validator

Flags schools with low match rate or unusual linkage behavior.

Rules:

1. Match rate below threshold.
2. Too many review pairs.
3. Duplicate endline matches.
4. Large grade progression mismatch among matches.

### 14.4 DQA Outputs

```text
data/outputs/dqa/dqa_issues.csv
data/outputs/dqa/dqa_summary_by_school.csv
data/outputs/dqa/dqa_summary_by_field.csv
data/outputs/dqa/dqa_summary_by_severity.csv
reports/dqa_summary.md
reports/dqa_summary.html
```

---

## 15. Record Linkage Design

### 15.1 Purpose

Link baseline and endline records when unique IDs are missing, inconsistent, or incomplete.

### 15.2 Matching Variables

| Variable | Use |
|---|---|
| Standardized name | Primary fuzzy matching feature |
| Sex | Agreement feature |
| Date of birth | Strong agreement feature |
| School ID | Blocking or exact restriction |
| Grade | Progression consistency |
| LRN | Deterministic matching when present and valid |

### 15.3 Blocking Rules

MVP blocking rules:

1. Same school and same LRN.
2. Same school and same date of birth.
3. Same school and same standardized surname.
4. Same school and same sex and same grade progression group.
5. Same municipality and same LRN for transfer cases.

### 15.4 Match Classification

| Match probability | Classification | Action |
|---:|---|---|
| >= 0.95 | `auto_match` | Include in panel |
| 0.80 to 0.95 | `review` | Include in clerical review queue |
| < 0.80 | `non_match` | Exclude from linked panel |

### 15.5 Linkage Outputs

```text
data/outputs/linkage/candidate_pairs.parquet
data/outputs/linkage/scored_pairs.parquet
data/outputs/linkage/auto_matches.parquet
data/outputs/linkage/review_queue.csv
data/outputs/linkage/linkage_summary_by_school.csv
reports/linkage_summary.md
```

### 15.6 Linkage Report Contents

1. Overall baseline records.
2. Overall endline records.
3. Number and share auto-matched.
4. Number and share requiring review.
5. Number and share unmatched.
6. Match rate by school.
7. Match probability distribution.
8. Most common reasons for linkage uncertainty.
9. Example anonymized review cases.

---

## 16. Panel Builder Design

### 16.1 Purpose

Create analysis-ready child and school panels from standardized records and linkage outputs.

### 16.2 Child Panel Build Logic

1. Start from auto-matched baseline-endline pairs.
2. Join baseline child fields.
3. Join endline child fields.
4. Join school master and treatment assignment.
5. Add derived variables.
6. Add DQA issue counts.
7. Add panel inclusion flags.
8. Export to Parquet and CSV.

### 16.3 Derived Variables

| Variable | Definition |
|---|---|
| `post` | 0 for baseline, 1 for endline |
| `treated` | School-level treatment flag |
| `measurement_gap_days` | Endline measurement date minus baseline measurement date |
| `delta_weight_kg` | Endline weight minus baseline weight |
| `delta_height_cm` | Endline height minus baseline height |
| `delta_bfaz` | Endline BFAZ minus baseline BFAZ |
| `delta_hfaz` | Endline HFAZ minus baseline HFAZ |
| `allocation_ratio` | Allocation base enrollment divided by current enrollment |
| `dilution_exposure` | `max(0, 1 - allocation_ratio)` |
| `has_critical_dqa_issue` | Any critical DQA issue on baseline or endline |
| `panel_inclusion_flag` | Passes basic inclusion rules |

### 16.4 Panel Inclusion Rules

A record is included in the main synthetic analysis-ready panel if:

1. Baseline and endline records are linked.
2. Match status is `auto_match`.
3. School ID is valid.
4. Treatment assignment is available.
5. Sex is non-missing.
6. Baseline age is valid.
7. At least one primary outcome is available.
8. No critical DQA issue exists for the selected outcome.

### 16.5 Outputs

```text
data/processed/child_panel.parquet
data/processed/child_panel.csv
data/processed/school_panel.parquet
data/processed/analysis_mart_long.parquet
data/processed/analysis_mart_wide.parquet
```

---

## 17. Reporting Design

### 17.1 Reports to Produce

| Report | File | Purpose |
|---|---|---|
| Ingestion report | `reports/ingestion_summary.md` | Shows files read, failed, and standardized |
| DQA report | `reports/dqa_summary.md` | Shows data quality issues |
| Linkage report | `reports/linkage_summary.md` | Shows match quality and review needs |
| Panel report | `reports/panel_summary.md` | Shows final panel counts |
| Evaluation-readiness report | `reports/evaluation_readiness_summary.md` | Explains whether synthetic data are ready for analysis demo |
| Portfolio walkthrough | `docs/portfolio_walkthrough.md` | Explains the project to external reviewers |

### 17.2 DQA Report Outline

```text
# Data Quality Report

## 1. Summary
## 2. Files Processed
## 3. Record Counts
## 4. Missingness by Field
## 5. Issues by Severity
## 6. Issues by School
## 7. Date Parsing Issues
## 8. Anthropometric Plausibility Checks
## 9. Duplicate and Near-Duplicate Records
## 10. Measurement Timing
## 11. Recommended Review Actions
```

### 17.3 Linkage Report Outline

```text
# Record Linkage Report

## 1. Summary
## 2. Baseline and Endline Record Counts
## 3. Blocking Rules Used
## 4. Match Probability Distribution
## 5. Match Outcomes
## 6. School-Level Match Rates
## 7. Review Queue Summary
## 8. Duplicate Match Warnings
## 9. Recommended Review Actions
```

---

## 18. Optional Dashboard Design

### 18.1 Dashboard Tool

Use Streamlit for the public demo because it is fast to build and easy to explain.

### 18.2 Dashboard Pages

| Page | Contents |
|---|---|
| Overview | Schools, children, files processed, match rate |
| Data Quality | Issues by severity, field, school, wave |
| Linkage | Match probability distribution, match rates |
| Panel | Final panel counts, inclusion funnel |
| School Explorer | School-level DQA and linkage profile |
| Methods | Explanation of synthetic data and privacy |

### 18.3 Dashboard Command

```bash
uv run streamlit run dashboards/streamlit_app.py
```

---

## 19. Command Line Interface Design

### 19.1 CLI Commands

```bash
uv run school-feeding generate-synthetic
uv run school-feeding ingest
uv run school-feeding validate
uv run school-feeding link
uv run school-feeding build-panel
uv run school-feeding report
uv run school-feeding run-all
```

### 19.2 Run-All Command

```bash
uv run school-feeding run-all \
  --config config/project.yml
```

Expected sequence:

1. Generate synthetic data.
2. Ingest raw data.
3. Validate records.
4. Run linkage.
5. Build panel.
6. Generate reports.

---

## 20. Configuration Design

### 20.1 `config/project.yml`

```yaml
project:
  name: school-feeding-data-engineering-demo
  version: 0.1.0
  seed: 20260614

paths:
  raw_dir: data/synthetic_raw
  reference_dir: data/synthetic_reference
  interim_dir: data/interim
  processed_dir: data/processed
  outputs_dir: data/outputs
  reports_dir: reports

synthetic:
  n_divisions: 3
  n_municipalities: 12
  n_schools: 120
  children_min: 80
  children_max: 350
  treatment_share: 0.5

linkage:
  auto_match_threshold: 0.95
  review_threshold: 0.80

validation:
  fail_on_critical_schema_error: true
  fail_on_empty_school_file: true
```

### 20.2 `config/dqa_rules.yml`

```yaml
ranges:
  weight_kg:
    min: 10
    max: 100
    severity: high
  height_cm:
    min: 70
    max: 200
    severity: high
  age_years_computed:
    min: 4
    max: 15
    severity: high
  bfaz:
    min: -6
    max: 6
    severity: medium
  hfaz:
    min: -6
    max: 6
    severity: medium

missingness:
  school_field_threshold:
    measurement_date: 0.10
    weight_kg: 0.10
    height_cm: 0.10

measurement_timing:
  min_gap_days: 60
  max_gap_days: 300
```

---

## 21. Testing Strategy

### 21.1 Test Types

| Test type | Purpose |
|---|---|
| Unit tests | Test individual functions |
| Integration tests | Test full pipeline on small data |
| Golden output tests | Ensure stable outputs for fixed seed |
| Schema tests | Ensure required columns exist |
| Regression tests | Prevent reintroduction of known bugs |
| CLI tests | Ensure commands work from terminal |

### 21.2 Minimum Test Coverage

MVP should include tests for:

1. Synthetic data generation is deterministic with fixed seed.
2. Required columns are generated.
3. Date parser handles ISO, month-day-year, timestamp, Excel serial, invalid, and blank dates.
4. Ingestion preserves raw values.
5. Schema validator catches missing columns.
6. Range validator catches implausible height and weight.
7. Duplicate validator catches exact and near duplicates.
8. Linkage produces expected matches on a tiny fixture.
9. Panel builder creates one row per linked child.
10. Run-all command completes on a small fixture.

### 21.3 Example Test Command

```bash
uv run pytest
```

---

## 22. GitHub Actions CI

### 22.1 CI Goals

1. Install dependencies.
2. Run linting.
3. Run tests.
4. Run small pipeline fixture.
5. Confirm reports are generated.

### 22.2 Example Workflow

```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync

      - name: Run tests
        run: uv run pytest

      - name: Run small pipeline fixture
        run: uv run school-feeding run-all --config config/project.yml
```

---

## 23. Makefile Design

```makefile
.PHONY: setup synthetic ingest validate link panel report test run-all clean

setup:
	uv sync

synthetic:
	uv run school-feeding generate-synthetic --config config/project.yml

ingest:
	uv run school-feeding ingest --config config/project.yml

validate:
	uv run school-feeding validate --config config/project.yml

link:
	uv run school-feeding link --config config/project.yml

panel:
	uv run school-feeding build-panel --config config/project.yml

report:
	uv run school-feeding report --config config/project.yml

test:
	uv run pytest

run-all:
	uv run school-feeding run-all --config config/project.yml

clean:
	rm -rf data/interim data/processed data/outputs reports/*.html reports/*.md
```

---

## 24. Documentation to Write

### 24.1 Required Documents

| Document | Purpose |
|---|---|
| `README.md` | Main public-facing explanation |
| `docs/technical_design_spec.md` | Full TDS |
| `docs/data_dictionary.md` | Canonical fields and data types |
| `docs/data_quality_rules.md` | Validation rules and severity |
| `docs/linkage_methodology.md` | Record linkage design |
| `docs/privacy_and_synthetic_data.md` | Explains why data are safe to publish |
| `docs/portfolio_walkthrough.md` | Explains how to review the project |
| `docs/future_work.md` | Stretch features and limitations |

### 24.2 README Outline

```text
# School Feeding Data Engineering Demo

## What this project does
## Why this matters
## What is synthetic and what is not
## Pipeline overview
## Quick start
## Repository structure
## Data model
## Data quality checks
## Record linkage
## Outputs
## Dashboard
## Tests
## Limitations
## Portfolio notes
```

### 24.3 Privacy Document Outline

```text
# Privacy and Synthetic Data

## Public-release principle
## What the synthetic data mimic
## What the synthetic data do not contain
## Fields intentionally excluded
## Re-identification risk controls
## How to verify the data are synthetic
## Responsible use
```

---

## 25. Implementation Plan

### Phase 0: Repository Setup

**Goal:** Establish a clean public project scaffold.

Tasks:

1. Create repository.
2. Add `.gitignore`.
3. Add `pyproject.toml`.
4. Add `uv` environment.
5. Add basic package structure.
6. Add `README.md` skeleton.
7. Add `Makefile`.
8. Add GitHub Actions CI skeleton.

Deliverables:

```text
README.md
pyproject.toml
Makefile
src/school_feeding_pipeline/
tests/
.github/workflows/ci.yml
```

Definition of done:

1. `uv sync` works.
2. `uv run pytest` works.
3. CI passes.

### Phase 1: Synthetic Data Generator

**Goal:** Generate safe raw school-level files.

Tasks:

1. Generate school master.
2. Generate treatment assignment.
3. Generate baseline child records.
4. Generate endline child records.
5. Inject attrition and transfer-in cases.
6. Inject data quality issues.
7. Write raw school CSV and XLSX files.

Deliverables:

```text
data/synthetic_raw/
data/synthetic_reference/
src/school_feeding_pipeline/synthetic/
tests/test_synthetic_generation.py
```

Definition of done:

1. Fixed seed produces deterministic outputs.
2. Raw files look like school submissions.
3. No real data are used.

### Phase 2: Ingestion and Standardization

**Goal:** Read raw school files into canonical tables.

Tasks:

1. Implement file discovery.
2. Implement CSV and XLSX readers.
3. Implement column alias mapping.
4. Implement raw value preservation.
5. Implement date parsing.
6. Export standardized Parquet files.

Deliverables:

```text
data/interim/baseline_standardized.parquet
data/interim/endline_standardized.parquet
data/interim/ingestion_log.csv
src/school_feeding_pipeline/ingest/
```

Definition of done:

1. All synthetic raw files are processed.
2. Failed files are logged.
3. Date parsing statuses are available.

### Phase 3: DQA Engine

**Goal:** Produce row-level and school-level data quality flags.

Tasks:

1. Implement validator interface.
2. Implement schema validator.
3. Implement completeness validator.
4. Implement range validator.
5. Implement consistency validator.
6. Implement duplicate validator.
7. Implement age-grade validator.
8. Implement measurement timing validator.
9. Export DQA issue tables.

Deliverables:

```text
data/outputs/dqa/dqa_issues.csv
data/outputs/dqa/dqa_summary_by_school.csv
reports/dqa_summary.md
src/school_feeding_pipeline/validate/
```

Definition of done:

1. DQA flags match intentionally injected errors.
2. Summary report is readable.
3. Tests cover each validator.

### Phase 4: Record Linkage

**Goal:** Link baseline and endline child records.

Tasks:

1. Prepare linkage inputs.
2. Configure Splink settings.
3. Run candidate generation.
4. Score pairs.
5. Classify matches.
6. Create review queue.
7. Generate linkage summary.

Deliverables:

```text
data/outputs/linkage/auto_matches.parquet
data/outputs/linkage/review_queue.csv
reports/linkage_summary.md
src/school_feeding_pipeline/linkage/
```

Definition of done:

1. Linkage completes on synthetic data.
2. Auto-match and review thresholds work.
3. Review queue is interpretable.

### Phase 5: Panel Builder

**Goal:** Build child and school panels.

Tasks:

1. Join matched baseline and endline records.
2. Add treatment assignment.
3. Add school master fields.
4. Add DQA issue counts.
5. Add derived variables.
6. Export panel tables.

Deliverables:

```text
data/processed/child_panel.parquet
data/processed/school_panel.parquet
data/processed/analysis_mart_long.parquet
data/processed/analysis_mart_wide.parquet
```

Definition of done:

1. One row per linked child in wide panel.
2. Long mart has baseline and endline rows.
3. Panel inclusion flags are documented.

### Phase 6: Reports and Dashboard

**Goal:** Make the project understandable to reviewers.

Tasks:

1. Generate ingestion report.
2. Generate DQA report.
3. Generate linkage report.
4. Generate panel report.
5. Build optional Streamlit dashboard.
6. Add screenshots to README.

Deliverables:

```text
reports/*.md
reports/*.html
dashboards/streamlit_app.py
docs/portfolio_walkthrough.md
```

Definition of done:

1. Reports can be regenerated from CLI.
2. Dashboard runs locally.
3. README explains outputs clearly.

### Phase 7: Polish and Public Release

**Goal:** Make the repository portfolio-ready.

Tasks:

1. Finalize README.
2. Add architecture diagram.
3. Add sample report screenshots.
4. Add license.
5. Add citation or attribution note.
6. Add limitations section.
7. Verify no confidential data exist.
8. Run final CI.

Deliverables:

```text
README.md
docs/privacy_and_synthetic_data.md
docs/portfolio_walkthrough.md
LICENSE
```

Definition of done:

1. Public clone can run the full demo.
2. No private files are included.
3. Project tells a clear portfolio story.

---

## 26. MVP Scope

The MVP should be deliberately limited.

### 26.1 MVP Must-Haves

1. Synthetic data generator.
2. Raw baseline and endline school files.
3. Ingestion and standardization.
4. Date parser.
5. DQA engine.
6. Basic probabilistic linkage.
7. Child panel builder.
8. Markdown reports.
9. Tests.
10. README.

### 26.2 MVP Nice-to-Haves

1. Streamlit dashboard.
2. dbt model layer.
3. HTML reports.
4. Dockerfile.
5. GitHub Pages documentation.

### 26.3 Exclude from MVP

1. Airflow.
2. Cloud deployment.
3. Full causal modeling.
4. Real data ingestion.
5. Complex GIS.
6. Authentication.
7. Production database.

---

## 27. Suggested Milestone Timeline

| Milestone | Scope | Estimated effort |
|---|---|---:|
| M0 | Repo setup and CI | 0.5 to 1 day |
| M1 | Synthetic data generator | 1 to 2 days |
| M2 | Ingestion and standardization | 1 to 2 days |
| M3 | DQA validators | 2 to 3 days |
| M4 | Record linkage | 2 to 3 days |
| M5 | Panel builder | 1 day |
| M6 | Reports and README | 1 to 2 days |
| M7 | Dashboard and polish | 1 to 2 days |

A strong MVP can be completed in about 9 to 16 focused workdays.

---

## 28. Key Design Decisions

### 28.1 Why synthetic data?

Synthetic data allows the project to be public while preserving confidentiality. It also gives full control over error injection, expected outputs, and testing.

### 28.2 Why Python-first?

The goal is data engineering. Python has strong tooling for file ingestion, validation, testing, and CLI development. R can be added later for optional statistical examples.

### 28.3 Why DuckDB?

DuckDB is lightweight, fast, and easy to run locally. It avoids the setup burden of Postgres while still demonstrating analytical database thinking.

### 28.4 Why Splink?

Splink demonstrates a serious real-world data engineering skill: probabilistic record linkage. This is more distinctive than ordinary cleaning.

### 28.5 Why not Airflow in the MVP?

Airflow adds operational overhead and distracts from the core portfolio value. A Makefile and CLI are sufficient for the public demo.

### 28.6 Why not publish causal estimates?

Synthetic causal estimates can mislead reviewers if presented as substantive. The project should focus on evaluation readiness, not policy conclusions.

---

## 29. Evaluation-Readiness Checks

The final report should answer these questions:

1. How many raw files were processed?
2. How many baseline and endline records were ingested?
3. What share of records passed core validation?
4. What were the most common data quality issues?
5. What share of baseline records linked to endline?
6. Which schools had low match rates?
7. How many records are in the final child panel?
8. Are treatment and control schools represented?
9. Are baseline and endline measurement dates plausible?
10. Which records should be excluded from a downstream analysis demo?

---

## 30. Portfolio Value

This project demonstrates the following skills:

| Skill | How the project demonstrates it |
|---|---|
| Data ingestion | Reads many messy school files |
| Schema harmonization | Maps inconsistent columns into canonical fields |
| Data validation | Flags missingness, invalid dates, outliers, and inconsistencies |
| Entity resolution | Links children across waves |
| Data modeling | Builds child, school, and analysis-ready panels |
| Reproducibility | Uses CLI, Makefile, tests, and CI |
| Documentation | Includes data dictionary, methodology, and reports |
| Privacy-aware release | Uses synthetic data and explicit governance notes |
| Public-sector relevance | Mirrors realistic administrative monitoring workflows |
| Evaluation literacy | Preserves school-level treatment and panel structure |

---

## 31. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Synthetic data look too fake | Inject realistic missingness, typos, date issues, and linkage uncertainty |
| Project becomes too large | Keep MVP focused on ingestion, DQA, linkage, and panel building |
| Reviewers misunderstand synthetic results | Clearly state that results are synthetic and not policy evidence |
| Linkage becomes too complex | Start with a tiny deterministic fixture, then add Splink |
| Reports become too text-heavy | Add concise tables and charts |
| Confidential data accidentally included | Use a clean public repo, never copy files from private repo |
| Tooling becomes overbuilt | Avoid Airflow and cloud until core pipeline is complete |

---

## 32. Security and Privacy Checklist

Before public release:

- [ ] No real learner names.
- [ ] No real LRNs.
- [ ] No real phone numbers.
- [ ] No real household addresses.
- [ ] No private raw Excel files.
- [ ] No confidential school-level operational files.
- [ ] No `.env` file.
- [ ] No API keys.
- [ ] No real audio or transcript files.
- [ ] No unreviewed screenshots from confidential reports.
- [ ] Synthetic data generation code is included.
- [ ] README clearly states data are synthetic.
- [ ] Privacy document explains what was excluded.
- [ ] Git history checked for accidental private files.

---

## 33. Suggested First Implementation Prompt

Use this prompt for a coding assistant or as your own implementation brief:

```text
You are helping build a public, privacy-safe data engineering portfolio project named school-feeding-data-engineering-demo.

Goal:
Build an MVP pipeline that generates synthetic school feeding monitoring data and transforms it into an analysis-ready child panel through ingestion, validation, probabilistic linkage, and reporting.

Requirements:
1. Use Python 3.11.
2. Use uv for dependency management.
3. Use pandas, duckdb, pyarrow, openpyxl, pydantic or pandera, typer, rich, pytest, and optionally splink.
4. Do not use real learner, school, household, or program records.
5. Generate synthetic baseline and endline school files.
6. Treatment assignment is at the school level.
7. Preserve raw values before parsing.
8. Implement robust date parsing, including ISO strings, month-day-year strings, timestamps, Excel serial dates, invalid dates, and ambiguous dates.
9. Implement validators for schema, completeness, ranges, duplicates, consistency, age-grade alignment, and measurement timing.
10. Implement a linkage step that links baseline and endline child records using synthetic name, sex, date of birth, school, grade, and optional LRN.
11. Build child_panel, school_panel, analysis_mart_long, and analysis_mart_wide.
12. Generate Markdown reports for ingestion, DQA, linkage, and panel construction.
13. Add unit tests and a GitHub Actions workflow.
14. Keep the MVP simple. Do not add Airflow or cloud deployment.

Deliverables:
- Repository scaffold.
- CLI commands: generate-synthetic, ingest, validate, link, build-panel, report, run-all.
- Config files under config/.
- Tests under tests/.
- Reports under reports/.
- Documentation under docs/.
- README with quick start instructions.

Style:
Write clean, modular code. Include type hints. Prefer small functions. Add docstrings where useful. Keep all outputs reproducible with a fixed seed.
```

---

## 34. Suggested README Quick Start

```bash
git clone https://github.com/<username>/school-feeding-data-engineering-demo.git
cd school-feeding-data-engineering-demo

uv sync

uv run school-feeding run-all --config config/project.yml

uv run pytest
```

Expected outputs:

```text
data/synthetic_raw/
data/interim/
data/outputs/
data/processed/
reports/dqa_summary.md
reports/linkage_summary.md
reports/panel_summary.md
```

---

## 35. Future Enhancements

After MVP, add the following in order:

1. Streamlit dashboard.
2. dbt-DuckDB transformation layer.
3. HTML reports using Quarto or Jinja.
4. Dockerfile.
5. GitHub Pages documentation.
6. Benchmark mode for larger synthetic datasets.
7. Manual review UI for linkage candidates.
8. Great Expectations or Pandera validation reports.
9. Simple R analysis demo with DiD structure.
10. Synthetic geospatial matching demo.

---

## 36. Final Recommended Build Order

The best build sequence is:

1. `README.md` skeleton.
2. `pyproject.toml` and package scaffold.
3. Synthetic data generator.
4. Ingestion.
5. Date parser.
6. DQA validators.
7. DQA report.
8. Linkage.
9. Panel builder.
10. Linkage and panel reports.
11. Tests and CI.
12. Dashboard and polish.

This order prevents overbuilding and ensures that every step produces something visible and reviewable.

---

## 37. Success Criteria

The project is successful if a public reviewer can:

1. Clone the repository.
2. Run one setup command.
3. Generate synthetic raw school files.
4. Run the full pipeline.
5. Inspect data quality issues.
6. Inspect linkage results.
7. Open the final child panel.
8. Understand why the project matters.
9. Confirm no confidential data are included.
10. See a clear connection between data engineering and evaluation readiness.

---

## 38. One-Sentence Portfolio Summary

```text
I built a privacy-safe data engineering pipeline that turns messy synthetic school feeding records into validated, linked, analysis-ready child panels, demonstrating ingestion, data quality assurance, probabilistic record linkage, reproducible reporting, and public-sector evaluation readiness.
```
