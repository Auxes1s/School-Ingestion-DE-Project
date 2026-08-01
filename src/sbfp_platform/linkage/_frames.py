"""Set row shapes for link runs, even with no match."""

from __future__ import annotations

import pandas as pd

CANDIDATE_COLUMNS = {
    "candidate_id": "string",
    "baseline_record_id": "string",
    "endline_record_id": "string",
    "school_id": "string",
    "method": "string",
    "pass_id": "string",
    "match_probability": "float64",
    "match_weight": "float64",
    "baseline_school_id": "string",
    "endline_school_id": "string",
    "ambiguous": "bool",
}

RESULT_COLUMNS = {
    "link_id": "string",
    "baseline_record_id": "string",
    "endline_record_id": "string",
    "school_id": "string",
    "method": "string",
    "match_probability": "float64",
    "decision": "string",
    "review_reason": "string",
    "transferred_flag": "bool",
    "source_method": "string",
    "pass_id": "string",
}


def typed_frame(rows: list[dict], columns: dict[str, str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for name, dtype in columns.items():
        if name not in frame:
            frame[name] = pd.Series(dtype=dtype)
        else:
            frame[name] = frame[name].astype(dtype)
    return frame[list(columns)]
