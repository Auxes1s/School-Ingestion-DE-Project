"""Link rows in a set order with exact rules."""

from __future__ import annotations

import pandas as pd

from sbfp_platform.linkage._frames import CANDIDATE_COLUMNS, typed_frame
from sbfp_platform.utils.hashing import stable_id


def _eligible(frame: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    for column in required:
        values = frame[column]
        mask &= values.notna() & values.astype("string").str.strip().ne("")
    return frame.loc[mask]


def generate_deterministic_candidates(
    baseline: pd.DataFrame, endline: pd.DataFrame, config: dict
) -> pd.DataFrame:
    """Run each pass in order and keep tied pairs for review."""
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for pass_number, rule in enumerate(config.get("passes", [])):
        pass_id = str(rule["pass_id"])
        keys = list(rule["keys"])
        required = list(rule.get("require_non_null", keys))
        joined = _eligible(baseline, required).merge(
            _eligible(endline, required), on=keys, suffixes=("_l", "_r"), how="inner"
        )
        if joined.empty:
            continue
        left_counts = joined.groupby("child_record_id_l")["child_record_id_r"].transform("nunique")
        right_counts = joined.groupby("child_record_id_r")["child_record_id_l"].transform("nunique")
        for position, item in joined.iterrows():
            baseline_id = str(item["child_record_id_l"])
            endline_id = str(item["child_record_id_r"])
            identity = (pass_id, baseline_id, endline_id)
            if identity in seen:
                continue
            seen.add(identity)
            baseline_school = str(item.get("school_id_l", item.get("school_id", "")))
            endline_school = str(item.get("school_id_r", item.get("school_id", "")))
            rows.append(
                {
                    "candidate_id": stable_id("candidate", *identity),
                    "baseline_record_id": baseline_id,
                    "endline_record_id": endline_id,
                    "school_id": baseline_school or None,
                    "method": "deterministic",
                    "pass_id": pass_id,
                    "match_probability": 1.0,
                    "match_weight": 30.0 - pass_number,
                    "baseline_school_id": baseline_school,
                    "endline_school_id": endline_school,
                    "ambiguous": bool(
                        left_counts.loc[position] > 1 or right_counts.loc[position] > 1
                    ),
                }
            )
    result = typed_frame(rows, CANDIDATE_COLUMNS)
    return result.sort_values(
        ["match_weight", "baseline_record_id", "endline_record_id"],
        ascending=[False, True, True],
        kind="stable",
    ).reset_index(drop=True)
