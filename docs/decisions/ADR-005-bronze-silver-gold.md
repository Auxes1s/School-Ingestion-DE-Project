# ADR-005: Bronze, silver, and gold boundaries

**Decision:** Preserve source fidelity in bronze, standardize and validate in silver,
and expose only de-identified analytical products in gold.

The layers create explicit audit, modeling, and sharing contracts. The extra materialized
boundary costs local disk space but makes reruns, row reconciliation, and privacy checks
independently testable.
