# Five-minute walkthrough

1. Start at the DQA page. It compares injected defects with detected issues, turning
   validation from an assertion into measured sensitivity and precision.
2. Open Linkage. Compare match rate with known-truth recall and inspect how threshold
   changes move precision, recall, F1, and review workload.
3. Note transfer recall. Cross-school movement exposes the ceiling imposed by per-school
   probabilistic blocking; the deterministic cross-school pass provides a controlled
   mitigation.
4. In Dagster, follow the non-linear silver → DQA/linkage → gold graph. dbt runs on both
   sides of Python entity resolution.
5. Trace a silver record back to its source file and row. Then inspect gold/export
   schemas to see that identity fields stop at the privacy boundary.

Run locally:

```bash
uv sync --extra dev
make pipeline PROFILE=tiny
make dashboard
```

For individual stages use `make generate`, `make ingest`, `make silver`, `make dqa`,
`make linkage`, `make gold`, and `make score`.
