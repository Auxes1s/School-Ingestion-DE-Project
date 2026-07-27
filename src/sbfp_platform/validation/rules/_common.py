"""Helpers shared by the rule modules.

Nothing here reads configuration or the filesystem: these are frame-shaped utilities so
each rule body stays a statement about the data rather than about pandas.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from typing import Any

import pandas as pd

from sbfp_platform.validation.issues import Issue, as_text

LRN_PATTERN = re.compile(r"^\d{12}$")


def blank(series: pd.Series) -> pd.Series:
    """True where a value is null, an empty string, or whitespace only."""
    if series.dtype.kind in "fiuM":
        return series.isna()
    empty = series.map(lambda v: isinstance(v, str) and not v.strip()).astype(bool)
    return (series.isna() | empty).astype(bool)


def present(series: pd.Series) -> pd.Series:
    """Complement of :func:`blank`."""
    return ~blank(series)


def column(df: pd.DataFrame, name: str) -> pd.Series:
    """Fetch a column, or an all-null column when the frame does not carry it.

    Silver schemas are ``strict=False``, so optional columns genuinely may be absent; a
    rule that depends on one should find nothing rather than raise.
    """
    if name in df.columns:
        return df[name]
    return pd.Series([None] * len(df), index=df.index, dtype=object)


def record_issues(
    df: pd.DataFrame,
    mask: pd.Series,
    *,
    field: str | None,
    message: str | Callable[[Any], str],
    values: pd.Series | None = None,
    action: str | None = None,
) -> Iterator[Issue]:
    """Emit one record-scope issue per masked row.

    ``record_id`` is the row's ``child_record_id``. That is the identifier
    ``truth_defects.record_id`` carries, and the DQA scorecard joins the two (spec §3.1),
    so populating it correctly is the difference between a measured detection rate and a
    zero.
    """
    if mask is None or not mask.any():
        return
    selected = mask.fillna(False).astype(bool)
    flagged = df.loc[selected]
    observed = list(values.loc[flagged.index]) if values is not None else [None] * len(flagged)

    for row, raw_value in zip(flagged.to_dict("records"), observed, strict=True):
        value = as_text(raw_value)
        yield Issue(
            message=message(value) if callable(message) else message,
            record_id=as_text(row.get("child_record_id")),
            source_file_id=as_text(row.get("source_file_id")),
            school_id=as_text(row.get("school_id")),
            period=as_text(row.get("period")),
            field_name=field,
            observed_value=value,
            suggested_action=action,
        )


def well_formed_lrn(series: pd.Series) -> pd.Series:
    """True where the value is exactly twelve digits."""
    return series.map(
        lambda v: isinstance(v, str) and bool(LRN_PATTERN.fullmatch(v.strip()))
    ).fillna(False)


def pair_waves(records: pd.DataFrame) -> pd.DataFrame:
    """Join each learner's baseline row to their endline row on a well-formed LRN.

    Linkage proper is slice 6 and is not available here, so the consistency rules use the
    one key that is unambiguous by construction: an LRN that appears exactly once in each
    period. LRNs appearing twice within a period are the duplicate rules' business, and
    pairing them here would manufacture spurious inconsistencies.

    Returns a frame with ``lrn`` plus every record column suffixed ``_baseline`` and
    ``_endline``.
    """
    usable = records[well_formed_lrn(column(records, "lrn_clean"))].copy()
    if usable.empty:
        return usable.head(0)

    usable["lrn_clean"] = usable["lrn_clean"].str.strip()
    counts = usable.groupby(["lrn_clean", "period"]).size().rename("n").reset_index()
    unique_keys = counts[counts["n"] == 1][["lrn_clean", "period"]]
    usable = usable.merge(unique_keys, on=["lrn_clean", "period"], how="inner")

    baseline = usable[usable["period"] == "baseline"]
    endline = usable[usable["period"] == "endline"]
    if baseline.empty or endline.empty:
        return usable.head(0)

    paired = baseline.merge(endline, on="lrn_clean", suffixes=("_baseline", "_endline"))
    return paired.rename(columns={"lrn_clean": "lrn"})
