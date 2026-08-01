# ADR-003: Dagster for cross-framework orchestration

**Decision:** Model Python generation/ingestion, two dbt stages, DQA, Splink, evaluation,
and exports as software-defined assets.

The key graph branches after silver and rejoins before gold. Dagster makes this lineage
and its materialization metadata visible while the same stage functions remain callable
from the CLI and tests.
