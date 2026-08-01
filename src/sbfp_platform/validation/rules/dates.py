"""Date rules: the value survived load, but its source form was suspect."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, timedelta

import pandas as pd

from sbfp_platform.validation.frames import CHILD_RECORDS
from sbfp_platform.validation.issues import Issue, RuleContext
from sbfp_platform.validation.parsing import DateShape, classify_date, raw_or_canonical
from sbfp_platform.validation.registry import rule
from sbfp_platform.validation.rules._common import record_issues

# Add this much slack to the set test dates. A file one term late is a late-file issue,
# not a false date. Only a far-off year is a false date.
_MEASUREMENT_SLACK_DAYS = 365


def _shapes(df: pd.DataFrame, field: str, ctx: RuleContext) -> pd.Series:
    """Sort the raw source cell behind field for every row."""
    raw = raw_or_canonical(df, field, dict(ctx.schema_registry))
    return raw.map(classify_date)


def _plausible_window(field: str, project: dict) -> tuple[date, date]:
    """Bounds a parsed value must fall inside to be considered possible. Use this rule as shown."""
    if field == "birthday_str":
        return (
            date(int(project["birth_year_min"]), 1, 1),
            date(int(project["birth_year_max"]), 12, 31),
        )
    earliest = pd.Timestamp(project["baseline_window"]["start"]).date()
    latest = pd.Timestamp(project["endline_window"]["end"]).date()
    return earliest - timedelta(days=_MEASUREMENT_SLACK_DAYS), latest + timedelta(
        days=_MEASUREMENT_SLACK_DAYS
    )


def _emit(
    df: pd.DataFrame,
    ctx: RuleContext,
    predicate: Callable[[str, DateShape], bool],
    message: Callable[[str, DateShape], str],
    action: str,
) -> Iterator[Issue]:
    """Run predicate over each set date field, emitting record-scope issues. Use this rule as shown. Use this rule as shown."""
    for field in ctx.spec.fields:
        shapes = _shapes(df, field, ctx)
        mask = shapes.map(
            lambda shape, field=field: not shape.blank and predicate(field, shape)
        ).astype(bool)
        yield from record_issues(
            df,
            mask,
            field=field,
            values=shapes.map(lambda shape: shape.raw),
            # ``classify_date`` caches its work. Read the shown text again so the note
            # stays next to the check that made it.
            message=lambda value, field=field: message(field, classify_date(value)),
            action=action,
        )


@rule("DQA_DATE_AMBIGUOUS_FORMAT", frame=CHILD_RECORDS)
def ambiguous_date_format(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """The source value parses under both DD/MM and MM/DD to two different dates. Use this rule as shown."""
    yield from _emit(
        df,
        ctx,
        predicate=lambda field, shape: shape.ambiguous,
        message=lambda field, shape: (
            f"{field} value {shape.raw!r} is valid as both DD/MM/YYYY and MM/DD/YYYY; "
            "the parser resolved it by precedence."
        ),
        action="Confirm the day/month order with the submitting school.",
    )


@rule("DQA_DATE_EXCEL_SERIAL", frame=CHILD_RECORDS)
def excel_serial_date(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """The cell arrived as a sheet serial number, or with a time component glued on. Use this rule as shown."""
    yield from _emit(
        df,
        ctx,
        predicate=lambda field, shape: shape.excel_serial or shape.timestamp_suffix,
        message=lambda field, shape: (
            f"{field} arrived as a spreadsheet serial number ({shape.raw!r})."
            if shape.excel_serial
            else f"{field} arrived with a time component appended ({shape.raw!r})."
        ),
        action="Format the source column as a date before export.",
    )


@rule("DQA_DATE_IMPOSSIBLE", frame=CHILD_RECORDS)
def impossible_date(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """The value cannot be load as a date, or lands outside the sound window."""
    project = dict(ctx.project)

    def outside(field: str, shape: DateShape) -> bool:
        low, high = _plausible_window(field, project)
        return shape.parsed is None or not (low <= shape.parsed <= high)

    def describe(field: str, shape: DateShape) -> str:
        low, high = _plausible_window(field, project)
        return (
            f"{field} value {shape.raw!r} is unreadable as a date or falls outside "
            f"{low.isoformat()}..{high.isoformat()}."
        )

    yield from _emit(
        df,
        ctx,
        predicate=outside,
        message=describe,
        action="Correct the date at source; the record cannot be aged or sequenced without it.",
    )
