# Referee report: Measured Trust — round 1

Date: 2026-08-01
Mode: code audit
Verdict: **Accept**

## Summary

This audit reviewed the trained-Splink redesign, synthetic generator, quality
pipeline, scorecards, privacy boundary, documentation, and reproducible public
artifacts. A clean tiny-profile rebuild completed successfully. The final state
passes 407 Python tests, 27 dbt tests, Ruff lint and format checks, the privacy
scanner, and zero-warning deck compiles.

## Audit 1: code correctness

- Splink trains once on the global baseline/follow-up population, persists a
  JSON model, and loads that model through a fresh linker for inference.
- Exact rules remain in the candidate artifact only as a benchmark. Production
  accepted links have `source_method = splink`.
- The resolver enforces mutual-best, one-to-one links and routes duplicated
  identifiers or close competing candidates to review.
- Missing values remain explicit throughout standardization and comparisons.
- The ground-truth answer key is isolated from ingestion, validation, linkage,
  dbt models, gold tables, and exports by AST, schema, and runtime tests.
- No major coding defect was found.

## Audit 2: independent replication

The model itself was not replicated in R or Stata because Splink is a
Python/DuckDB entity-resolution implementation rather than an econometric
estimator with equivalent cross-language packages. Instead, the operating
scorecard was independently recomputed with set-based DuckDB SQL in
`code/replication/referee2_replicate_linkage.sql`.

| Method | True links | False links | Recall | F1 | Transfer recall |
|---|---:|---:|---:|---:|---:|
| Exact-rule benchmark | 556 | 0 | 0.631818 | 0.774373 | 0.269231 |
| Trained Splink | 812 | 0 | 0.922727 | 0.959811 | 0.730769 |

All independently recomputed values match the pipeline scorecard to within
`1e-12`.

## Audit 3: replication package

Replication readiness: **9/10**.

- Paths are repository-relative and configuration-backed.
- Dependencies are locked in `uv.lock`.
- Seed 2026 reproduces the tiny proof case.
- `make pipeline PROFILE=tiny` is the master clean-room workflow.
- Generated data, lakehouse files, reports, and exports are ignored and rebuilt
  locally; deck sources and final publication artifacts are versioned.
- The local readability utility remains diagnostic rather than a CI gate because
  its strict per-fragment Flesch threshold misclassifies technical tables,
  identifiers, and extracted slide fragments.

## Audit 4: output automation

- Scorecards, reports, exports, dashboard metrics, figures, and evidence tables
  are programmatically generated.
- The showcase deck and publication card compile with zero errors, warnings, or
  box overflows.
- README and slide narrative numbers are intentionally rendered as publication
  copy; regression tests and the independent SQL audit protect the underlying
  values.

## Audit 5: econometrics

Not applicable. This repository prepares linkage-safe evaluation data but does
not estimate or claim a causal program effect.

## Pre-push findings resolved

1. Removed a plain-language CI command that was guaranteed to fail on the
   current technical corpus; the tested audit utility remains available locally.
2. Applied Ruff formatting to eight files that would have failed CI.
3. Restored the DQA regression floor from 85% to 90%; the clean run achieves
   90.75%.
4. Ignored disposable TeX intermediates while retaining source and final PDFs.
5. Added an independent SQL scorecard replication.

## Remaining limitations

- The performance threshold is tuned on a fixed synthetic benchmark and must be
  recalibrated for real data.
- Seven of 26 planted cross-group moves remain unresolved.
- The audit verifies linkage accuracy, reproducibility, and privacy—not program
  impact validity.

## Verdict

**Accept.** No major concern remains before push.
