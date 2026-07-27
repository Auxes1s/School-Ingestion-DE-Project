"""Completeness rules: a field the program depends on is absent.

Every rule here is record scope, so every issue carries the offending row's
``child_record_id``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sbfp_platform.contracts import SEXES
from sbfp_platform.validation.frames import CHILD_RECORDS, MEASUREMENTS
from sbfp_platform.validation.issues import Issue, RuleContext
from sbfp_platform.validation.registry import rule
from sbfp_platform.validation.rules._common import blank, column, record_issues


@rule("DQA_COMPLETENESS_MISSING_LRN", frame=CHILD_RECORDS)
def missing_lrn(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """LRN absent. Without it, deterministic linkage falls back to name matching."""
    lrn = column(df, "lrn_clean")
    yield from record_issues(
        df,
        blank(lrn),
        field="lrn_clean",
        message="Learner reference number is missing.",
        action="Recover the LRN from the school register before the record is linked.",
    )


@rule("DQA_COMPLETENESS_MISSING_BIRTH_DATE", frame=CHILD_RECORDS)
def missing_birth_date(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """Birth date absent. Age-for-height indicators cannot be computed without it."""
    birthday = column(df, "birthday_str")
    yield from record_issues(
        df,
        blank(birthday),
        field="birthday_str",
        message="Birth date is missing.",
        action="Recover the date of birth from the learner's record.",
    )


@rule("DQA_COMPLETENESS_MISSING_SEX", frame=CHILD_RECORDS)
def missing_sex(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """Sex absent or outside the recognized vocabulary.

    Anything the value-normalization step in ``configs/schema_registry.yml`` could not
    fold to ``Male``/``Female`` counts as missing: an unrecognized value is as unusable
    for sex-disaggregated reporting as an empty cell.
    """
    sex = column(df, "sex")
    unusable = blank(sex) | ~sex.isin(list(SEXES))
    yield from record_issues(
        df,
        unusable,
        field="sex",
        values=sex,
        message=lambda value: (
            "Sex is missing." if value is None else f"Sex value {value!r} is not recognized."
        ),
        action="Normalize to Male/Female, or recover the value from the school register.",
    )


@rule("DQA_COMPLETENESS_MISSING_HEIGHT", frame=MEASUREMENTS)
def missing_height(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """Height absent, so the child contributes to no anthropometric indicator."""
    height = column(df, "height_cm")
    yield from record_issues(
        df,
        blank(height),
        field="height_cm",
        message="Height was not recorded for this measurement.",
        action="Re-measure, or exclude the record from anthropometric indicators.",
    )


@rule("DQA_COMPLETENESS_MISSING_WEIGHT", frame=MEASUREMENTS)
def missing_weight(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """Weight absent, so the child contributes to no anthropometric indicator."""
    weight = column(df, "weight_kg")
    yield from record_issues(
        df,
        blank(weight),
        field="weight_kg",
        message="Weight was not recorded for this measurement.",
        action="Re-measure, or exclude the record from anthropometric indicators.",
    )
