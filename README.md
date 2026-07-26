# School Feeding Data Platform

A privacy-safe, public-sector data engineering platform for school feeding monitoring
and evaluation. It simulates messy school submissions and transforms them into trusted
data products through a local lakehouse, orchestrated ingestion, data quality checks,
probabilistic record linkage, tested transformations, and dashboard-ready marts.

**All data is synthetic.** No real learner records are present anywhere in this
repository. See `docs/privacy_and_synthetic_data.md`.

---

## What makes this different

Most data quality projects assert that their validation works. This one **measures it**.

Because the data is synthetic, the generator knows the right answer. It writes a hidden
ground-truth answer key alongside the messy source files — every injected defect, and
every baseline↔endline pair that genuinely exists. The pipeline never sees it. Only the
evaluation layer does, and a test enforces that separation.

That buys two scorecards that a real pipeline structurally cannot produce:

- **DQA scorecard** — for every validation rule: how many defects were injected, how
  many were caught, how many false positives were raised. Detection rate and precision
  per rule.
- **Linkage scorecard** — true precision, recall, and F1 for deterministic vs.
  probabilistic matching, swept across thresholds. Real linkage pipelines can only ever
  report *match rate*, because nobody knows the true answer.

The linkage scorecard also reports the **transfer recall ceiling**: the generator injects
pupils who move schools between waves, and per-school blocking cannot find them by
construction. That limitation is published rather than hidden.

---

## Status

Under active construction. Build slices, in order:

| # | Slice | Status |
|---|---|---|
| 1 | Skeleton, frozen config + schema contracts, CLI, CI | ✅ |
| 2 | Synthetic generator + ground truth | ⬜ |
| 3 | Bronze ingestion, manifest, schema drift log | ⬜ |
| 4 | DQA engine + DQA scorecard | ⬜ |
| 5 | dbt silver + gold marts | ⬜ |
| 6 | Record linkage + linkage scorecard | ⬜ |
| 7 | Dagster orchestration | ⬜ |
| 8 | Streamlit command center | ⬜ |
| 9 | Documentation and polish | ⬜ |

---

## Quickstart

```bash
uv sync --extra dev
make doctor                 # verify config contracts and dependencies
make pipeline PROFILE=demo  # generate → ingest → silver → dqa → linkage → gold → score
make dashboard              # Streamlit command center
```

### Scale profiles

| Profile | Schools | Children | Runtime |
|---|---:|---:|---|
| `tiny` | 5 | 1,000 | < 30s (CI) |
| `demo` | 40 | 12,000 | 2–4 min (default) |
| `large` | 150 | 50,000 | opt-in |

One seed drives all randomness: the same seed and profile reproduce byte-identical
source files. No generated data is committed — `make generate` reproduces it.

---

## Architecture

```
Python generator   →  synthetic_raw/  +  ground_truth/   (answer key, pipeline never reads)
Python ingestion   →  bronze/         hash, manifest, schema drift, date parsing
dbt (DuckDB)       →  silver_*        standardize, normalize
Python linkage     →  linkage/        deterministic → Splink → review queue
dbt (DuckDB)       →  gold_*          evaluation panel, monitoring marts
Python evaluation  →  scorecards      gold ⨝ ground truth
Dagster            →  asset graph across all of the above
Streamlit          →  DQA command center
```

Linkage sits deliberately between the two dbt stages: it cannot be expressed in SQL, and
gold depends on it.

---

## Domain grounding

The synthetic data models the real engineering problem of a school-based feeding program
impact evaluation in BARMM, Philippines. Canonical field names (`lrn_clean`,
`student_name_clean`, `first_letter_name`, `birthday_str`), the per-school Splink loop,
and the 0.75 accept / 0.65 review thresholds mirror that real pipeline so the synthetic
problem is recognizably the real one. No data, records, or confidential material from
that work appear here.

---

## License

MIT
