# ADR-006: Code-only synthetic release

**Decision:** Commit generation code and fixed policy, but generate raw data and answer
keys on demand.

This avoids publishing sensitive material, keeps repository size small, and proves
reproducibility. Byte-identical fixed-seed generation and CI metric floors protect the
demo from silent drift.
