"""Rule implementations.

Importing this package registers every rule. The engine imports it once, then looks
implementations up by ``rule_id``; nothing else should call the rule functions directly
except the unit tests, which exercise them in isolation.

One module per rule category, matching the categories in ``configs/dqa_rules.yml``.
"""

from __future__ import annotations

from sbfp_platform.validation.rules import (  # noqa: F401  (imported for registration)
    completeness,
    consistency,
    dates,
    duplicates,
    program,
    quality,
    reference,
    validity,
)

__all__ = [
    "completeness",
    "consistency",
    "dates",
    "duplicates",
    "program",
    "quality",
    "reference",
    "validity",
]
