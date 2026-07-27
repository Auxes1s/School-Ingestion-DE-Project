"""Validity and range rules: the value is present but cannot be right.

Range bounds come from ``thresholds`` in ``configs/dqa_rules.yml``. They are read through
the context, never restated here, so widening a bound is a config change rather than a
code change.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sbfp_platform.validation.frames import CHILD_RECORDS, MEASUREMENTS
from sbfp_platform.validation.issues import Issue, RuleContext
from sbfp_platform.validation.registry import rule
from sbfp_platform.validation.rules._common import column, present, record_issues, well_formed_lrn


@rule("DQA_VALIDITY_MALFORMED_LRN", frame=CHILD_RECORDS)
def malformed_lrn(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """LRN present but not the canonical twelve digits.

    Deliberately disjoint from the missing-LRN rule: a blank LRN is a completeness
    problem, and double-flagging it would inflate both rules' issue counts.
    """
    lrn = column(df, "lrn_clean")
    malformed = present(lrn) & ~well_formed_lrn(lrn)
    yield from record_issues(
        df,
        malformed,
        field="lrn_clean",
        values=lrn,
        message=lambda value: f"LRN {value!r} is not 12 digits.",
        action="Correct the LRN at source; do not pad or truncate it in the pipeline.",
    )


def _out_of_range(values: pd.Series, bounds: dict) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.notna() & ((numeric < bounds["min"]) | (numeric > bounds["max"]))


@rule("DQA_RANGE_IMPLAUSIBLE_HEIGHT", frame=MEASUREMENTS)
def implausible_height(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """Height outside the biologically plausible range for a school-age child."""
    bounds = ctx.threshold("height_cm")
    height = column(df, "height_cm")
    yield from record_issues(
        df,
        _out_of_range(height, bounds),
        field="height_cm",
        values=height,
        message=lambda value: (
            f"Height {value} cm is outside the plausible range {bounds['min']}-{bounds['max']} cm."
        ),
        action="Check for a unit error (metres recorded as centimetres) or a transcription slip.",
    )


@rule("DQA_RANGE_IMPLAUSIBLE_WEIGHT", frame=MEASUREMENTS)
def implausible_weight(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """Weight outside the biologically plausible range for a school-age child."""
    bounds = ctx.threshold("weight_kg")
    weight = column(df, "weight_kg")
    yield from record_issues(
        df,
        _out_of_range(weight, bounds),
        field="weight_kg",
        values=weight,
        message=lambda value: (
            f"Weight {value} kg is outside the plausible range {bounds['min']}-{bounds['max']} kg."
        ),
        action="Check for a decimal-point error or a transcription slip.",
    )
