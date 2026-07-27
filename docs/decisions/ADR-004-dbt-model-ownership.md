# ADR-004: dbt owns set-based transformations

**Decision:** dbt builds standardized silver entities and privacy-safe gold marts;
Python owns heterogeneous file parsing, procedural validation, and probabilistic linkage.

This split keeps SQL models reviewable and testable without forcing entity resolution or
spreadsheet handling into SQL. Linkage therefore sits between silver and gold dbt runs.
