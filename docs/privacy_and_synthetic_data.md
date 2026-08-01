# Privacy and synthetic data

All names, learner identifiers, schools, measurements, and program observations are
generated. They do not reproduce official records or impact estimates. Names are built
from a small fictional syllable grammar rather than copied from people; learner numbers
are synthetic and exist only to exercise validation and linkage.

The platform still behaves as if the inputs were sensitive:

- generated raw data and answer keys are ignored by Git;
- the answer key is outside the lakehouse and readable only by evaluation code;
- gold tables and public exports prohibit names, learner identifiers, and raw payloads;
- public serving reads only gold aggregates and de-identified panels;
- CI scans for accidental sensitive-looking files and identifier values;
- a production deployment should add role-based access, encryption, retention policy,
  audit logging, and small-cell suppression before publishing aggregates.

The answer key makes performance measurable, not available to the algorithms being
measured. Structural and runtime tests protect that distinction.

## Threat model

| Threat | Control in this repository | Production addition |
|---|---|---|
| Real records committed accidentally | Git ignores generated data; CI scans identifiers, emails, filenames | Pre-receive DLP and incident process |
| Answer key leaks into algorithms | Separate directory/package, AST import/literal tests, dbt scan | Separate storage account and role |
| Identity reaches public products | Forbidden-column contracts and runtime gold/export scans | Column-level access policy |
| Small groups reveal individuals | Synthetic public data only | Cell suppression and disclosure review |
| Unauthorized source access | No real sources are present | Encryption, RBAC, audit logs, retention limits |
| Stale or altered files create duplicate truth | Hash/version manifest and idempotent bronze writes | Object-lock/versioned source landing zone |
