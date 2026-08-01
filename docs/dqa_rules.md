# Data-quality rules

Rules are registered in `configs/dqa_rules.yml`; code refuses to run if config and
implementations diverge. Each finding has a severity, scope, source lineage, affected
field, suggested action, and resolution state.

The rule families cover required schema, missing and malformed identity fields, raw date
ambiguity and Excel serials, impossible dates, exact and LRN duplicates, anthropometric
ranges and missingness, cross-wave height/sex/birthdate consistency, digit heaping,
school-name drift, timeliness, and allocation dilution.

The DQA scorecard is a real classification evaluation:

- true positive: the expected rule detects the injected defect's record;
- false negative: a detectable injected defect is not found;
- false positive: a finding has no matching injected defect for that rule and record;
- defects marked `expected_detectable=false` are reported in truth but excluded from
  sensitivity because no honest rule can distinguish them from legitimate values.

## Registry

| Rule | Severity | Scope | Reviewer action |
|---|---|---|---|
| Required column missing | Critical | File | Return file or approve a registry alias |
| Missing / malformed LRN | High | Record | Correct identifier or retain for probabilistic linkage |
| Missing birth date | High | Record | Recover from source register |
| Missing sex | Medium | Record | Verify against source register |
| Ambiguous date format | Medium | Record | Confirm locale interpretation |
| Excel/timestamp date | Low | Record | Standardize the source export |
| Impossible date | Critical | Record | Correct before analysis |
| Exact duplicate | High | Record | Retain one source row |
| Duplicate LRN/name variant | High | Record | Resolve competing identity rows |
| Implausible height / weight | Critical | Record | Re-measure or correct units |
| Missing height / weight | High | Record | Complete anthropometry |
| Height decreases across waves | High | Child | Check units, dates, and transcription |
| Sex / birthdate differs across waves | High | Child | Resolve linked identity conflict |
| Digit heaping | Medium | School-period | Audit measurement practice/device |
| School-name drift | Low | File | Join by ID and correct the source label |
| Late submission | Medium | File | Follow up with submitting office |
| Enrollment exceeds allocation | Medium | School | Re-base the next allocation |

Exact rule IDs, target fields, thresholds, and defect mappings remain in
`configs/dqa_rules.yml`; the engine fails closed if a configured rule lacks code.
