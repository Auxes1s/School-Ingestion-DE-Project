"""Health data rules: the values are individually sound but collectively wrong. Use this rule as shown. Use this rule as shown. Keep this rule in place."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sbfp_platform.validation.frames import MEASUREMENTS
from sbfp_platform.validation.issues import Issue, RuleContext, as_text
from sbfp_platform.validation.registry import rule

# Do not judge a school with less than this many health facts. In a set of ten, three
# values can end in zero by chance. A larger set misses a few true cases but cuts false
# alerts, which is the safer trade.
MIN_GROUP_SIZE = 20


def _terminal_digit_share(values: pd.Series) -> float:
    """Share of values whose nearest-centimetre (or kilogram) terminal digit is 0 or 5. Use this rule as shown. Use this rule as shown. Keep this rule in place."""
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return 0.0
    terminal = numeric.round().abs().astype("int64") % 10
    return float(terminal.isin((0, 5)).mean())


@rule("DQA_MEASUREMENT_DIGIT_HEAPING", frame=MEASUREMENTS)
def digit_heaping(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """Terminal digits within a school-period cluster on 0 and 5. Use this rule as shown. Use this rule as shown."""
    threshold = float(ctx.threshold("digit_heaping_threshold"))
    if df.empty or not {"school_id", "period"} <= set(df.columns):
        return

    for (school_id, period), group in df.groupby(["school_id", "period"], dropna=False):
        for field in ctx.spec.fields:
            if field not in group.columns:
                continue
            values = pd.to_numeric(group[field], errors="coerce").dropna()
            if len(values) < MIN_GROUP_SIZE:
                continue
            share = _terminal_digit_share(values)
            if share <= threshold:
                continue
            yield Issue(
                message=(
                    f"{share:.0%} of {field} values in this school-period end in 0 or 5 "
                    f"across {len(values)} measurements, above the {threshold:.0%} threshold "
                    "expected from honest measurement."
                ),
                school_id=as_text(school_id),
                period=as_text(period),
                field_name=field,
                observed_value=f"{share:.3f}",
                suggested_action=(
                    "Retrain or re-supervise the measuring team; treat the session's "
                    "anthropometry as low precision."
                ),
            )
