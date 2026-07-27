"""Reference and schema rules: the submission disagrees with the registry it belongs to.

Both rules are file scope. ``record_id`` stays null — the finding is about a file, not
about any learner in it — and ``source_file_id`` carries the identity instead.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sbfp_platform.validation.frames import CHILD_RECORDS, SCHEMA_DRIFT, SCHOOLS
from sbfp_platform.validation.issues import Issue, RuleContext, as_text
from sbfp_platform.validation.parsing import raw_or_canonical
from sbfp_platform.validation.registry import rule

#: The drift class this rule reports. The other classes in the drift log (unmapped and
#: missing-optional columns) are recorded by ingestion but are not data-quality failures.
_MISSING_REQUIRED = "missing_required"


@rule("DQA_SCHEMA_REQUIRED_COLUMN_MISSING", frame=SCHEMA_DRIFT)
def schema_required_column_missing(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """A required canonical column could not be mapped from a source file.

    Ingestion already recorded the drift; this rule promotes it into the issue registry
    so that a file arriving without, say, a birth-date column is visible in the same
    place as every other quality finding rather than only in a bronze-layer log.
    """
    if df.empty or "drift_type" not in df.columns:
        return

    missing = df[df["drift_type"] == _MISSING_REQUIRED]
    for row in missing.to_dict("records"):
        column_name = as_text(row.get("column_name_raw")) or "unknown column"
        yield Issue(
            message=(
                f"Required column {column_name!r} could not be mapped from this file; "
                "every row in it is incomplete."
            ),
            source_file_id=as_text(row.get("source_file_id")),
            field_name=as_text(row.get("mapped_to")) or column_name,
            observed_value=column_name,
            suggested_action=(
                "Return the file to the submitting office, or add the header variant to "
                "configs/schema_registry.yml if it is legitimate."
            ),
        )


@rule("DQA_REFERENCE_SCHOOL_NAME_DRIFT", frame=CHILD_RECORDS, requires=(SCHOOLS,))
def school_name_drift(df: pd.DataFrame, ctx: RuleContext) -> Iterator[Issue]:
    """The school name written on a submission is not the masterlist name.

    Compared exactly, and on purpose: name drift is how one school becomes three rows in
    an aggregate report, so the point is to notice the drift, not to forgive it. The
    comparison uses the most common raw spelling in each file, which keeps one mistyped
    row from being reported as the file's name.
    """
    masterlist = ctx.frame(SCHOOLS)
    if df.empty or masterlist.empty or "school_name" not in masterlist.columns:
        return

    official = masterlist.set_index("school_id")["school_name"].to_dict()
    submitted = raw_or_canonical(df, "school_name", dict(ctx.schema_registry))

    work = pd.DataFrame(
        {
            "source_file_id": df.get("source_file_id"),
            "school_id": df.get("school_id"),
            "submitted": submitted,
        }
    ).dropna(subset=["submitted"])
    if work.empty:
        return

    for (source_file_id, school_id), group in work.groupby(
        ["source_file_id", "school_id"], dropna=False
    ):
        expected = official.get(school_id)
        if expected is None:
            continue
        observed = group["submitted"].mode()
        if observed.empty:
            continue
        observed_name = str(observed.iloc[0])
        if observed_name == str(expected):
            continue
        yield Issue(
            message=(
                f"School name {observed_name!r} does not match the masterlist name "
                f"{expected!r} for {school_id}."
            ),
            source_file_id=as_text(source_file_id),
            school_id=as_text(school_id),
            field_name="school_name",
            observed_value=observed_name,
            suggested_action="Join on school_id, not name; correct the name at source.",
        )
