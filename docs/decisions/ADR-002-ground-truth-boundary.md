# ADR-002: Separate answer key from the pipeline

**Decision:** Generate truth alongside sources but store it outside the lakehouse and
permit reads only from the evaluation package.

This makes DQA and linkage accuracy measurable without leaking labels into the systems
being evaluated. An AST invariant test and dbt source scan enforce the boundary.
