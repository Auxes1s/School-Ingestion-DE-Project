# Design: School Feeding Data Platform

**Date:** 2026-07-26
**Status:** Approved
**Supersedes scope of:** `school_feeding_data_platform_tds.md` §31 (MVP)
**Repo:** `School-Ingestion DE Project` → `github.com/Auxes1s/School-Ingestion-DE-Project`

---

## 1. Purpose

Build a public, privacy-safe data engineering platform that turns messy synthetic
school-feeding submissions into trusted, analysis-ready data products.

The platform is modeled on a real evaluation pipeline (SBFP Impact Evaluation, Lanao
del Sur II) but shares **no data with it**. The real repository is a realism reference
only: field names, defect classes, linkage strategy, and threshold conventions are
mirrored so the synthetic problem is recognizably the real problem.

### 1.1 Scope decision

v1 covers TDS Phases 0–8, not the §31 MVP. Splink, Dagster, and dbt are all in v1.
This was an explicit choice, made with the size tradeoff stated. Mitigation is the
slice sequencing in §9: every slice ends with something that runs.

---

## 2. The central idea: a hidden answer key

`generate` writes two trees:

| Path | Read by | Contents |
|---|---|---|
| `data/synthetic_raw/` | the pipeline | messy Excel/CSV, what a school would actually submit |
| `data/ground_truth/` | **evaluation only** | the answer key |

Because the data is synthetic, ground truth exists. This is the platform's
differentiator: correctness claims are *measured*, not asserted.

### 2.1 Ground-truth tables

**`truth_children.parquet`** — one row per true child, pre-corruption.

| Field | Type | Notes |
|---|---|---|
| `true_child_id` | string | stable synthetic identity |
| `true_lrn` | string | pre-corruption LRN |
| `true_name` | string | pre-corruption full name |
| `true_birth_date` | date | pre-corruption DOB |
| `true_sex` | string | `Male` / `Female` |
| `baseline_school_id` | string | school at baseline |
| `endline_school_id` | string | null if attrited; differs if transferred |
| `attrited` | bool | true if no endline record exists |
| `transferred` | bool | true if endline school differs from baseline |

**`truth_links.parquet`** — one row per link that *should* be found.

| Field | Type |
|---|---|
| `true_child_id` | string |
| `baseline_record_id` | string |
| `endline_record_id` | string |
| `transferred` | bool |

Only non-attrited children appear. This table is the denominator for recall.

**`truth_defects.parquet`** — one row per injected defect.

| Field | Type | Notes |
|---|---|---|
| `defect_id` | string | |
| `record_id` | string | affected raw record |
| `field_name` | string | affected field, null for row-level defects |
| `defect_type` | string | matches a DQA rule id where a rule is expected to catch it |
| `original_value` | string | value before corruption |
| `corrupted_value` | string | value written to the raw file |
| `expected_detectable` | bool | false for defects no rule can reasonably catch |

`expected_detectable` keeps the DQA scorecard honest: a defect that no rule targets
must not count against detection rate.

### 2.2 Leak prevention

Ground truth leaking into the pipeline would invalidate every metric. Enforced structurally:

1. `data/ground_truth/` lives outside `data/lakehouse/`.
2. Only `src/sbfp_platform/evaluation/` may read it.
3. A pytest AST-scans every module under `src/sbfp_platform/{synthetic,ingestion,validation,linkage,transforms,observability}` and fails if any imports `evaluation` or references a ground-truth path.
4. dbt models may not reference ground-truth sources; enforced by the same test scanning `dbt/models/`.

Note: `synthetic/` *writes* ground truth but must not read it back during any pipeline
stage. The test allows `synthetic/` to write to the path and forbids the others entirely.

---

## 3. The two scorecards

### 3.1 DQA scorecard (`gold_dqa_scorecard`)

Joins `silver_dqa_issues` against `truth_defects` per rule.

| Field | Definition |
|---|---|
| `rule_id` | DQA rule identifier |
| `injected_count` | defects of this type with `expected_detectable = true` |
| `detected_count` | true positives |
| `missed_count` | false negatives |
| `false_positive_count` | issues raised where no defect was injected |
| `detection_rate` | `detected_count / injected_count` |
| `precision` | `detected_count / (detected_count + false_positive_count)` |

This is the README headline. It converts "I wrote validation rules" into "my
validation rules are 98.8% sensitive at 99.1% precision."

### 3.2 Linkage scorecard (`gold_linkage_scorecard`)

Computed per `(method, threshold)` where method ∈ {`deterministic`, `splink`, `combined`}.

| Field | Definition |
|---|---|
| `true_positives` | accepted links present in `truth_links` |
| `false_positives` | accepted links absent from `truth_links` |
| `false_negatives` | `truth_links` rows with no accepted link |
| `precision`, `recall`, `f1` | standard |
| `match_rate` | accepted links / baseline records — the *only* metric the real pipeline could compute |
| `review_queue_size` | pairs in the gray zone |

**Recall denominator is `truth_links`, not baseline records.** Children who genuinely
attrited (retention 0.88) are true non-matches. Conflating these is the most likely
way to produce a flattering, wrong number.

**Transfer ceiling.** The generator injects school transfers. Per-school blocking
(what the real pipeline does) structurally cannot find them, so the scorecard will show
a recall ceiling below 1.0. This is reported, not hidden — a measured limitation of the
architecture is stronger evidence of engineering judgment than a clean number.

---

## 4. Layer ownership

```
Python generator   →  synthetic_raw/  +  ground_truth/
Python ingestion   →  bronze/*.parquet     (hash, manifest, drift, date parsing)
dbt (DuckDB)       →  silver_*             (standardize, normalize)
Python linkage     →  linkage/*.parquet    (deterministic → Splink → review queue)
dbt (DuckDB)       →  gold_*               (panel, marts; consumes silver + linkage)
Python evaluation  →  gold_*_scorecard     (gold ⨝ ground_truth)
Dagster            →  asset graph over all of the above
Streamlit          →  reads gold from DuckDB
```

**Rule:** Python owns procedural work (Excel parsing, fuzzy matching, EM training).
dbt owns set-based work, so its schema tests cover the modeling layer. Dagster is the
only component that knows the full ordering.

The dbt → Python → dbt sandwich is deliberate. Linkage cannot be expressed in SQL, and
gold depends on it. Dagster handles this hop natively, and the resulting asset graph is
more interesting than a linear dbt DAG.

---

## 5. Canonical schema

Silver child records use the **real LDS II field names** so the synthetic work is
recognizably the same problem:

| Field | Type | Source of name |
|---|---|---|
| `child_record_id` | string | platform |
| `school_id` | string | platform |
| `period` | string | `baseline` \| `endline` |
| `lrn_clean` | string | real pipeline |
| `student_name_clean` | string | real pipeline |
| `first_letter_name` | string | real pipeline (blocking key) |
| `birthday_str` | string | real pipeline (ISO) |
| `sex` | string | real pipeline |
| `grade` | string | platform |
| `source_file_id` | string | platform |
| `source_row_number` | int | platform |

Measurements, schools, allocations, and DQA issues follow TDS §10.

---

## 6. Date parser contract

A direct port of the real `standardize_birthday()` behavior. Highest-value unit-test
target in the codebase.

Must handle: numeric Excel serials, string-encoded serials (`"43262"`),
`MM/DD/YYYY`, `DD/MM/YYYY`, `MM-DD-YYYY`, `DD-MM-YYYY`, ISO, `YYYY/MM/DD`,
2-digit years, timestamp-suffixed strings (`2019-02-17 00:00:00`), blanks, garbage.

Returns a struct, never a bare date:

```python
ParsedDate(
    raw_value: str,
    parsed_date: date | None,
    rule_used: str,        # e.g. "excel_serial", "mdy_slash"
    confidence: float,     # 1.0 unambiguous, <1.0 when DD/MM vs MM/DD is ambiguous
    issue_flag: str | None # e.g. "ambiguous_dmy", "out_of_range", "unparseable"
)
```

Ambiguity is recorded, never silently resolved. Plausible-year guard: reject outside
the configured birth-year window.

---

## 7. Scale profiles

| Profile | Schools | Children | Target runtime | Used by |
|---|---:|---:|---|---|
| `tiny` | 5 | 1,000 | < 30s | CI, integration tests |
| `demo` | 40 | 12,000 | 2–4 min | default `make pipeline` |
| `large` | 150 | 50,000 | opt-in | README scaling claim |

One seed drives all randomness. Same seed ⇒ byte-identical raw files.
Splink instantiates a fresh `DuckDBAPI()` inside each per-school loop, matching the
real pipeline's known constraint.

---

## 8. Testing and CI

**Unit:** date parser, column-alias mapper, each DQA rule in isolation, file hashing,
name standardization.

**Integration:** `tiny` profile end-to-end, bronze idempotency (re-ingest is a no-op),
schema-drift capture.

**dbt:** uniqueness, not-null, relationships, accepted values, row-count reconciliation.

**Three invariant tests** — the interesting ones:

1. **Privacy** — no raw-name column appears in any gold table or export.
2. **Leak** — no pipeline module imports `evaluation` or references a ground-truth path (§2.2).
3. **Regression** — scorecard metrics on the `tiny` fixed seed must not fall below
   committed floors. A change that quietly degrades linkage recall or DQA detection
   fails CI.

**CI order:** ruff → pytest → tiny generate → full pipeline → dbt build → PII scan.

---

## 9. Build slices

Each slice ends with something that runs, is tested, and is committable.

| # | Slice | Depends on | Ends with |
|---|---|---|---|
| 1 | Skeleton: package, **frozen config + schema contracts**, CLI, ruff, pytest, CI | — | `sbfp-platform doctor` passes in CI |
| 2 | Generator + ground truth | 1 | `make generate` produces messy files + answer key |
| 3 | Bronze ingestion + manifest + drift log | 1 (contracts) | re-running ingest is a no-op |
| 4 | DQA engine + DQA scorecard | 1 (contracts) | measured detection rate per rule |
| 5 | dbt silver + gold marts + schema tests | 3, 4 | `dbt build` green |
| 6 | Linkage + linkage scorecard | 5 | precision/recall/F1 by method and threshold |
| 7 | Dagster assets | 2–6 | full pipeline runs from the asset graph |
| 8 | Streamlit command center | 5, 6 | six TDS §20.1 pages, scorecards front and center |
| 9 | Docs, ADRs, README, screenshots | all | reviewer understands it in 5 min |

**Early-exit point:** slices 1–4 alone are a publishable repo with the headline feature
intact.

**Parallelism enabler:** slice 1 freezes all config files and schema contracts. Slices
2, 3, and 4 then build against those contracts using committed fixtures rather than
each other's live output, so they can proceed concurrently.

---

## 10. Repository structure

Follows TDS §9, with `evaluation/` added:

```
src/sbfp_platform/
├── cli.py
├── config.py           # loads configs/, validates, exposes profiles
├── contracts.py        # canonical schemas (Pandera) — frozen in slice 1
├── synthetic/          # generator + ground truth writer
├── ingestion/          # discovery, excel reader, alias mapper, date parser, bronze writer
├── validation/         # DQA rules + issue registry
├── linkage/            # deterministic, splink, review queue
├── transforms/         # dbt invocation wrappers, exports
├── evaluation/         # ONLY module allowed to read ground_truth/
├── observability/      # run logger, metrics
├── privacy/            # PII scanner, masking
└── utils/              # io, hashing, dates, logging
```

Plus `configs/`, `dbt/`, `orchestration/dagster_project/`, `dashboards/`, `tests/`,
`docs/`, `outputs/`.

---

## 11. Non-goals

Per TDS §5. Additionally, v1 does not deploy to cloud, does not implement OpenLineage,
and does not build a FastAPI serving layer. Docker is deferred to v2.

---

## 12. Definition of done

1. `uv sync && make generate && make pipeline` works from a clean clone.
2. Bronze, silver, and gold layers materialize.
3. Both scorecards produce measured numbers.
4. Dagster asset graph runs the full pipeline.
5. Streamlit dashboard loads all six pages against gold.
6. `make test` and CI pass, including the three invariant tests.
7. No real data anywhere; PII scanner clean.
8. README leads with the DQA command center.
