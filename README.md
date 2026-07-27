# School Feeding Data Platform

A privacy-safe public-sector data platform that turns messy synthetic school
submissions into measured, analysis-ready outputs. It combines Python ingestion and
validation, dbt/DuckDB transformations, real Splink entity resolution, Dagster assets,
and a Streamlit data-quality command center.

**All data is generated on demand. No real learner or school records are included.**

## The headline: quality you can measure

Most portfolio pipelines assert that their checks work. This one generates a hidden
answer key—every injected defect and every true baseline/endline pair—then evaluates the
finished pipeline without exposing that key to it.

Tiny fixed-seed demo results:

| Result | Value |
|---|---:|
| Schools / source files | 5 / 13 |
| Baseline + endline records | 1,918 |
| DQA rules executed | 21 / 21 |
| Combined accepted links | 827 |
| Linkage precision @ 0.75 | **100.0%** |
| Linkage recall @ 0.75 | **94.0%** |
| Linkage F1 @ 0.75 | **96.9%** |
| Transfer recall | **88.5%** |

The dashboard leads with the **DQA scorecard**: injected, detected, missed, and false
positive counts per rule. The linkage page separates match rate from known-truth recall
and sweeps thresholds so precision, recall, F1, and review workload are visible rather
than implied.

## Run it

Requirements: Python 3.11–3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
make doctor PROFILE=tiny
make pipeline PROFILE=tiny   # generate → bronze → silver → DQA/linkage → gold → score
make dashboard               # http://localhost:8501
```

The default `demo` profile has 40 schools and 12,000 children. The fixed-seed `tiny`
profile (5 schools, 1,000 children) is the CI smoke test; `large` is an opt-in 150-school,
50,000-child scale run. Generated source data, answer keys, lakehouse files, and exports
are Git-ignored and reproducible.

Useful commands:

```bash
make generate PROFILE=tiny   # messy CSV/XLSX + answer key
make ingest PROFILE=tiny     # idempotent hash-based bronze ingestion
make silver PROFILE=tiny     # dbt silver models and tests
make dqa PROFILE=tiny        # 21 config-backed quality rules
make linkage PROFILE=tiny    # deterministic passes + per-school Splink
make gold PROFILE=tiny       # privacy-safe marts
make score PROFILE=tiny      # measured DQA and linkage scorecards
make export PROFILE=tiny     # CSV + Parquet public products
make dagster                 # observable eight-asset graph
make test && make lint
```

Docker users can run `docker compose run --rm pipeline`, followed by
`docker compose up dashboard`.

## Architecture

```text
Python generator   → synthetic_raw/ + answer key (outside the lakehouse)
Python ingestion   → bronze/        manifests, hashes, drift, date provenance
dbt + DuckDB       → silver_*       standardized entities and measurements
                     ├─ Python DQA  → silver_dqa_issues
                     └─ Splink      → candidates, one-to-one results, review queue
dbt + DuckDB       → gold_*         panel, monitoring, exposure, quality marts
Python evaluation  → scorecards     pipeline outputs joined to answer key
Dagster            → 8 assets       the complete cross-framework dependency graph
Streamlit          → 6 pages        privacy-safe command center
```

The answer key is structurally isolated: only `sbfp_platform.evaluation` may read it.
AST tests prevent pipeline imports or path literals, dbt models are scanned, and runtime
tests reject learner names, LRNs, or raw payloads in gold and exports.

The generator and ingester independently derive the same source identity:
`record_id = SHA256(source_file_id|source_row_number)[:16]`. This makes every quality
finding traceable to a source row and every detection score reproducible without leaking
labels into validation.

## What is demonstrated

| Data-engineering area | Implementation |
|---|---|
| Generation | Deterministic synthetic world, messy schema/date variants, controlled defects |
| Ingestion | CSV/XLSX discovery, idempotency, version history, drift and error logs |
| Storage/modeling | Parquet lakehouse, DuckDB, two-stage dbt graph, 27 dbt tests |
| Data quality | 21 severity/scope-aware rules and measured detection scorecard |
| Entity resolution | Three deterministic passes, Splink 4 EM, global one-to-one resolver |
| Orchestration | Dagster assets branching after silver and rejoining before gold |
| Serving | Six-page Streamlit command center and dual CSV/Parquet exports |
| DataOps | pytest regression floors, Ruff, GitHub Actions, Docker, privacy scan |

## Repository map

```text
configs/                    frozen scale, schema, DQA, and linkage policy
src/sbfp_platform/          generator, ingestion, validation, linkage, evaluation
dbt/                        staging, silver, gold models and tests
orchestration/              Dagster definitions, jobs, schedule
dashboards/                 Streamlit command center
tests/                      unit, integration, privacy, and score regression tests
docs/                       architecture, contracts, lineage, DQA, privacy, ADRs
```

Start with [architecture](docs/architecture.md), [data contracts](docs/data_contracts.md),
[lineage](docs/data_lineage.md), [DQA rules](docs/dqa_rules.md), and the
[five-minute walkthrough](docs/portfolio_walkthrough.md). The executable schemas in
`src/sbfp_platform/contracts.py` remain authoritative.

## Honest limitations

- Splink runs per school, matching the reference workflow; transfers are only recovered
  by the explicit cross-school deterministic pass, so transfer recall is reported.
- This is a local public demo, not a managed multi-user warehouse. A real deployment
  still needs encrypted storage, access control, retention policy, and small-cell
  suppression.
- Synthetic scorecards measure engineering behavior, not official program impact.

Licensed under the [MIT License](LICENSE).
