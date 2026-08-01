"""Rule code. Importing this package registers every rule. Use this rule as shown. Use this rule as shown."""

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
