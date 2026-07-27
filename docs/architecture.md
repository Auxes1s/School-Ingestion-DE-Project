# Architecture

The platform deliberately crosses framework boundaries where each tool is strongest:
Python handles file parsing, validation, and entity resolution; dbt owns set-based
modeling; Dagster records the dependency graph; Streamlit serves only privacy-safe gold
tables.

```mermaid
flowchart LR
  G[Python generator] --> R[Messy CSV/XLSX]
  G -. evaluation only .-> T[Answer key]
  R --> B[Bronze Parquet]
  B --> S[dbt silver]
  S --> Q[Python DQA]
  S --> L[Deterministic + Splink]
  Q --> O[dbt gold]
  L --> O
  O --> E[Measured scorecards]
  T -. evaluation join .-> E
  E --> D[Streamlit / exports]
```

The answer key is outside the lakehouse. Pipeline packages cannot import the evaluation
package or reference that path literally; an AST test enforces the boundary. Each raw
record is traceable by `source_file_id` and `source_row_number`. The stable `record_id`
derived from those values is the only bridge used later to measure DQA detection.

Dagster exposes eight assets: source generation, bronze, silver, issue registry,
linkage, gold, scorecards, and exports. The CLI uses the same functions, so orchestration
does not conceal a second implementation.
