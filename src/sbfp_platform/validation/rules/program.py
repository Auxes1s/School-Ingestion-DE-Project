"""Timeliness and program rules: findings about how the program is running.

Neither is about a learner, so neither populates ``record_id``. Late submission is file
scope and keyed by ``source_file_id``; ration dilution is school scope and keyed by
``school_id``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sbfp_platform.validation.frames import ALLOCATIONS, CHILD_RECORDS, FILE_MANIFEST
from sbfp_platform.validation.issues import Issue, RuleContext, as_text
from sbfp_platform.validation.registry import rule

#: Manifest columns that can stand in for "when the school submitted", best first.
_SUBMITTED_AT_COLUMNS = ("modified_at", "discovered_at", "ingested_at")


def _window_close(period: str, project: dict) -> pd.Timestamp | None:
    window = project.get(f"{period}_window")
    if not window:
        return None
    return pd.Timestamp(window["end"])


def _period_by_file(records: pd.DataFrame) -> dict[str, str]:
    """Map each source file to the reporting period its rows belong to."""
    if records.empty or not {"source_file_id", "period"} <= set(records.columns):
        return {}
    counts = records.groupby(["source_file_id", "period"]).size().reset_index(name="n")
    ranked = counts.sort_values("n", ascending=False).drop_duplicates("source_file_id")
    return dict(zip(ranked["source_file_id"], ranked["period"], strict=True))


@rule("DQA_TIMELINESS_LATE_SUBMISSION", frame=FILE_MANIFEST, requires=(CHILD_RECORDS,))
def late_submission(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """A file arrived after its reporting window closed, plus the grace period.

    The window comes from ``configs/project.yml`` and the grace period from
    ``late_submission_grace_days``. The period a file belongs to is taken from the rows
    it produced rather than from the manifest's filename guess, because the rows are
    evidence and the guess is a heuristic.
    """
    if df.empty:
        return
    grace = pd.Timedelta(days=int(ctx.threshold("late_submission_grace_days")))
    project = dict(ctx.project)

    periods = _period_by_file(ctx.frame(CHILD_RECORDS))
    submitted_column = next((c for c in _SUBMITTED_AT_COLUMNS if c in df.columns), None)
    if submitted_column is None:
        return

    for row in df.to_dict("records"):
        source_file_id = as_text(row.get("source_file_id"))
        period = periods.get(source_file_id) or as_text(row.get("period_guess"))
        if period is None:
            continue
        close = _window_close(period, project)
        if close is None:
            continue
        submitted_at = (
            pd.Timestamp(row.get(submitted_column))
            if row.get(submitted_column) is not None
            else None
        )
        if submitted_at is None or pd.isna(submitted_at):
            continue
        deadline = close + grace
        if submitted_at <= deadline:
            continue
        days_late = (submitted_at.normalize() - deadline.normalize()).days
        yield Issue(
            message=(
                f"Submission arrived {days_late} day(s) after the {period} window closed "
                f"on {close.date().isoformat()} plus {grace.days} days of grace."
            ),
            source_file_id=source_file_id,
            school_id=as_text(row.get("school_id_guess")),
            period=period,
            field_name=submitted_column,
            observed_value=submitted_at.isoformat(),
            suggested_action=(
                "Follow up with the school; late data cannot be used for in-cycle targeting."
            ),
        )


@rule("DQA_PROGRAM_ENROLLMENT_EXCEEDS_ALLOCATION", frame=ALLOCATIONS)
def enrollment_exceeds_allocation(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """More children are enrolled than the allocation was sized for.

    Nothing is wrong with the data — this is a finding about the program. The rice is
    divided among everyone present, so an allocation base that lags enrollment dilutes
    the ration below its nominal per-child amount, and the dilution is invisible in any
    report that looks at allocation alone.
    """
    if df.empty or not {"allocated_children", "current_enrollment"} <= set(df.columns):
        return

    allocated = pd.to_numeric(df["allocated_children"], errors="coerce")
    enrolled = pd.to_numeric(df["current_enrollment"], errors="coerce")
    exceeded = allocated.notna() & enrolled.notna() & (allocated > 0) & (enrolled > allocated)

    for row in df[exceeded].to_dict("records"):
        base = float(row["allocated_children"])
        current = float(row["current_enrollment"])
        yield Issue(
            message=(
                f"Enrollment {current:.0f} exceeds the allocation base {base:.0f} "
                f"(ration diluted to {base / current:.0%} of nominal)."
            ),
            school_id=as_text(row.get("school_id")),
            field_name="current_enrollment",
            observed_value=f"{current:.0f}",
            suggested_action=(
                "Re-base the allocation on the current enrollment snapshot before the next "
                "delivery tranche."
            ),
        )
