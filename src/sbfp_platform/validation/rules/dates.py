"""Date rules: the value survived ingestion, but its source form was suspect.

These rules work from the raw source cell recovered out of ``raw_payload_json`` rather
than from the normalized silver value — see :mod:`sbfp_platform.validation.parsing`. A
date that ingestion silently resolved is exactly the date a reviewer needs to see.

Which fields a rule inspects comes from its ``fields`` list in ``configs/dqa_rules.yml``,
so adding a date column to a rule is a config edit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, timedelta

import pandas as pd

from sbfp_platform.validation.frames import CHILD_RECORDS
from sbfp_platform.validation.issues import Issue, RuleContext
from sbfp_platform.validation.parsing import DateShape, classify_date, raw_or_canonical
from sbfp_platform.validation.registry import rule
from sbfp_platform.validation.rules._common import record_issues

#: Slack around the configured measurement windows. A submission a season late is a
#: timeliness problem, not an impossible date; only wildly wrong years are impossible.
_MEASUREMENT_SLACK_DAYS = 365


def _shapes(df: pd.DataFrame, field: str, ctx: RuleContext) -> pd.Series:
    """Classify the raw source cell behind ``field`` for every row."""
    raw = raw_or_canonical(df, field, dict(ctx.schema_registry))
    return raw.map(classify_date)


def _plausible_window(field: str, project: dict) -> tuple[date, date]:
    """Bounds a parsed value must fall inside to be considered possible."""
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
    """Run ``predicate`` over each configured date field, emitting record-scope issues.

    Blank cells are never flagged here: an empty birth date is a completeness problem,
    and flagging it twice would double-count one defect.
    """
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
            # classify_date is memoized, so re-deriving the shape from the observed
            # value costs nothing and keeps the message next to its predicate.
            message=lambda value, field=field: message(field, classify_date(value)),
            action=action,
        )


@rule("DQA_DATE_AMBIGUOUS_FORMAT", frame=CHILD_RECORDS)
def ambiguous_date_format(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """The source value parses under both DD/MM and MM/DD to two different dates.

    Whichever reading ingestion picked, the other was equally defensible. The platform
    records the ambiguity instead of pretending it resolved one (spec §6).
    """
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
    """The cell arrived as a spreadsheet serial number, or with a time component glued on.

    Both are the same underlying failure — a date that was never stored as a date — and
    the rule registry maps both defect types to this rule.
    """
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
    """The value cannot be read as a date, or lands outside the plausible window.

    The window comes from ``configs/project.yml``: the birth-year guard for birth dates,
    and the program's measurement windows (with a year of slack) for measurement dates.
    """
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
