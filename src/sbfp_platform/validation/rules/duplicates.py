"""Duplicate rules.

Both rules flag every member of a duplicate group **except the first** by source row
number. That choice is deliberate: the first occurrence is the record the school meant to
submit, and flagging it too would double every detection and halve the rule's reported
precision.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sbfp_platform.utils.text import normalize_name
from sbfp_platform.validation.frames import CHILD_RECORDS
from sbfp_platform.validation.issues import Issue, RuleContext
from sbfp_platform.validation.registry import rule
from sbfp_platform.validation.rules._common import column, record_issues, well_formed_lrn

#: Columns that identify a submitted row when no raw payload survives. Deliberately
#: excludes platform-assigned keys (``child_record_id``, ``source_row_number``), which
#: are unique by construction and would make every row look distinct.
_ROW_CONTENT_COLUMNS = (
    "school_id",
    "period",
    "lrn_clean",
    "student_name_clean",
    "birthday_str",
    "sex",
    "grade",
)


def _ordered(df: pd.DataFrame) -> pd.DataFrame:
    """Rows in submission order, so 'first occurrence' means first in the file."""
    if "source_row_number" in df.columns:
        return df.sort_values("source_row_number", kind="stable")
    return df


def _row_signature(df: pd.DataFrame) -> pd.Series:
    """A per-row content fingerprint.

    Two rows match only if both their canonical content and their raw payloads match.
    ``raw_payload_json`` is the row as submitted, so equal payloads within a file are the
    byte-identical rows the rule is looking for — but requiring the canonical fields to
    agree as well means a payload that happens to carry only a subset of the columns
    cannot turn two different learners into a duplicate. Rows with no payload fall back
    to the canonical content alone.
    """
    payload = column(df, "raw_payload_json").fillna("")
    canonical = (
        df.reindex(columns=list(_ROW_CONTENT_COLUMNS))
        .astype("object")
        .apply(lambda row: "|".join("" if pd.isna(v) else str(v) for v in row), axis=1)
    )
    return canonical.str.cat(payload.astype(str), sep="␟")


@rule("DQA_DUPLICATE_EXACT_ROW", frame=CHILD_RECORDS)
def duplicate_exact_row(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """The same row content appears more than once inside one source file."""
    if df.empty:
        return
    ordered = _ordered(df)
    keys = pd.DataFrame(
        {
            "source_file_id": column(ordered, "source_file_id").fillna(""),
            "signature": _row_signature(ordered),
        },
        index=ordered.index,
    )
    repeated = keys.duplicated(keep="first")
    yield from record_issues(
        ordered,
        repeated,
        field=None,
        message="Row is identical to an earlier row in the same source file.",
        action="Deduplicate at source; keep the first occurrence.",
    )


@rule("DQA_DUPLICATE_LRN_WITHIN_SCHOOL_PERIOD", frame=CHILD_RECORDS)
def duplicate_lrn_within_school_period(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """One LRN appears on more than one learner row in a school-period, under a
    different name each time.

    Requiring the name to vary is what separates this from an exact duplicate: identical
    rows are the previous rule's business, whereas an LRN attached to two spellings is
    either a typo in the LRN or two children sharing one identifier, and both need a
    human.
    """
    if df.empty:
        return
    ordered = _ordered(df)
    lrn = column(ordered, "lrn_clean")
    usable = well_formed_lrn(lrn)
    if not usable.any():
        return

    work = pd.DataFrame(
        {
            "school_id": column(ordered, "school_id").fillna(""),
            "period": column(ordered, "period").fillna(""),
            "lrn": lrn.where(usable),
            "name": column(ordered, "student_name_clean").map(normalize_name),
        },
        index=ordered.index,
    )
    grouped = work[usable].groupby(["school_id", "period", "lrn"], dropna=True)
    varying = grouped["name"].transform("nunique") > 1
    repeated = work[usable].duplicated(subset=["school_id", "period", "lrn"], keep="first")

    mask = pd.Series(False, index=ordered.index)
    mask.loc[work[usable].index] = (varying & repeated).to_numpy()

    yield from record_issues(
        ordered,
        mask,
        field="lrn_clean",
        values=work["lrn"],
        message=lambda value: (
            f"LRN {value!r} already appears in this school-period under a different name."
        ),
        action="Confirm whether these are two learners or one; correct the LRN at source.",
    )
