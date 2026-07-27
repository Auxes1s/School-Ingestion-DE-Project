"""Cross-wave consistency rules.

Each of these compares a learner's baseline row to their endline row. Linkage is slice 6
and is not available here, so the pairing key is a well-formed LRN that occurs exactly
once per period — see :func:`sbfp_platform.validation.rules._common.pair_waves`.

**Which record the issue is filed against.** One issue per pair, filed against the
*endline* ``child_record_id``: that is the wave where the anomaly shows up (a height that
went down, a sex that changed), and filing against both rows would double-count a single
defect and halve the rule's precision.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sbfp_platform.validation.frames import CHILD_RECORDS, MEASUREMENTS
from sbfp_platform.validation.issues import Issue, RuleContext, as_text
from sbfp_platform.validation.parsing import classify_date
from sbfp_platform.validation.registry import rule
from sbfp_platform.validation.rules._common import pair_waves

#: Endline period label used on cross-wave issues.
_ENDLINE = "endline"


def _endline_issue(pair: dict, message: str, field: str, observed: object) -> Issue:
    return Issue(
        message=message,
        record_id=as_text(pair.get("child_record_id_endline")),
        source_file_id=as_text(pair.get("source_file_id_endline")),
        school_id=as_text(pair.get("school_id_endline")),
        period=_ENDLINE,
        field_name=field,
        observed_value=as_text(observed),
    )


def _first_measurement(measurements: pd.DataFrame, field: str) -> pd.Series:
    """First non-null ``field`` per ``child_record_id``, as a lookup Series."""
    if measurements.empty or field not in measurements.columns:
        return pd.Series(dtype="float64")
    usable = measurements[["child_record_id", field]].dropna(subset=[field])
    return usable.groupby("child_record_id")[field].first()


@rule("DQA_CONSISTENCY_HEIGHT_DECREASE", frame=MEASUREMENTS, requires=(CHILD_RECORDS,))
def height_decrease(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """Endline height is below baseline height by more than measurement tolerance.

    Children do not shrink. A small decrease is measurement noise, which is what
    ``height_decrease_tolerance_cm`` absorbs; beyond it, one of the two heights is wrong.
    """
    tolerance = float(ctx.threshold("height_decrease_tolerance_cm"))
    pairs = pair_waves(ctx.frame(CHILD_RECORDS))
    if pairs.empty:
        return

    heights = _first_measurement(df, "height_cm")
    baseline = pairs["child_record_id_baseline"].map(heights)
    endline = pairs["child_record_id_endline"].map(heights)
    drop = baseline - endline
    flagged = pairs[(drop.notna()) & (drop > tolerance)]

    for pair, loss in zip(flagged.to_dict("records"), drop.loc[flagged.index], strict=True):
        endline_height = heights.get(pair["child_record_id_endline"])
        baseline_height = heights.get(pair["child_record_id_baseline"])
        yield _endline_issue(
            pair,
            message=(
                f"Endline height {endline_height} cm is {loss:.1f} cm below baseline "
                f"{baseline_height} cm, beyond the {tolerance} cm tolerance."
            ),
            field="height_cm",
            observed=endline_height,
        )


@rule("DQA_CONSISTENCY_SEX_ACROSS_WAVES", frame=CHILD_RECORDS)
def sex_across_waves(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """The same learner is recorded as a different sex at baseline and endline."""
    pairs = pair_waves(df)
    if pairs.empty:
        return

    baseline = pairs["sex_baseline"]
    endline = pairs["sex_endline"]
    differing = baseline.notna() & endline.notna() & (baseline != endline)

    for pair in pairs[differing].to_dict("records"):
        yield _endline_issue(
            pair,
            message=(
                f"Sex differs across waves for LRN {pair['lrn']}: "
                f"{pair['sex_baseline']} at baseline, {pair['sex_endline']} at endline."
            ),
            field="sex",
            observed=pair["sex_endline"],
        )


@rule("DQA_CONSISTENCY_BIRTHDATE_ACROSS_WAVES", frame=CHILD_RECORDS)
def birthdate_across_waves(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """The same learner is recorded with a different birth date at baseline and endline.

    Compared as parsed dates where both waves parse, so a format difference between two
    submissions is not mistaken for a disagreement about the date.
    """
    pairs = pair_waves(df)
    if pairs.empty:
        return

    for pair in pairs.to_dict("records"):
        left = classify_date(pair.get("birthday_str_baseline"))
        right = classify_date(pair.get("birthday_str_endline"))
        if left.blank or right.blank:
            continue
        if left.readings and right.readings:
            # Intersect rather than compare: a value written DD/MM in one wave and MM/DD
            # in the other is a format ambiguity, which the date rules already report.
            # Calling it a birth-date disagreement too would be a false positive here.
            differs = not set(left.readings) & set(right.readings)
        else:
            differs = (left.raw or "").strip() != (right.raw or "").strip()
        if not differs:
            continue
        yield _endline_issue(
            pair,
            message=(
                f"Birth date differs across waves for LRN {pair['lrn']}: "
                f"{left.raw!r} at baseline, {right.raw!r} at endline."
            ),
            field="birthday_str",
            observed=right.raw,
        )
