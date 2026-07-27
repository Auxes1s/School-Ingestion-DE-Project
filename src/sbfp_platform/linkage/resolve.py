"""Combined one-to-one resolution across deterministic and Splink candidates."""

from __future__ import annotations

import pandas as pd

from sbfp_platform.linkage._frames import RESULT_COLUMNS, typed_frame
from sbfp_platform.utils.hashing import stable_id


def _collapse_pairs(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    ranked = candidates.assign(
        _method_rank=candidates["method"].map({"deterministic": 1, "splink": 0}).fillna(0)
    ).sort_values(
        ["match_probability", "_method_rank", "match_weight", "candidate_id"],
        ascending=[False, False, False, True],
        kind="stable",
    )
    return ranked.drop_duplicates(["baseline_record_id", "endline_record_id"], keep="first").drop(
        columns="_method_rank"
    )


def resolve_candidates(
    candidates: pd.DataFrame, *, accept_threshold: float, review_floor: float
) -> pd.DataFrame:
    """Choose accepted links globally and route ambiguous/gray pairs to review."""
    if not 0 <= review_floor <= accept_threshold <= 1:
        raise ValueError("Expected 0 <= review_floor <= accept_threshold <= 1")
    pairs = _collapse_pairs(candidates)
    if pairs.empty:
        return typed_frame([], RESULT_COLUMNS)

    above_accept = pairs.loc[pairs["match_probability"] >= accept_threshold]
    baseline_competition = above_accept["baseline_record_id"].value_counts()
    endline_competition = above_accept["endline_record_id"].value_counts()
    used_baseline: set[str] = set()
    used_endline: set[str] = set()
    rows: list[dict] = []

    ranked = pairs.sort_values(
        ["match_probability", "match_weight", "baseline_record_id", "endline_record_id"],
        ascending=[False, False, True, True],
        kind="stable",
    )
    for item in ranked.to_dict("records"):
        baseline_id = str(item["baseline_record_id"])
        endline_id = str(item["endline_record_id"])
        probability = float(item["match_probability"])
        endpoint_used = baseline_id in used_baseline or endline_id in used_endline
        competing = bool(item["ambiguous"]) or (
            item["method"] != "deterministic"
            and (
                baseline_competition.get(baseline_id, 0) > 1
                or endline_competition.get(endline_id, 0) > 1
            )
        )
        reason: str | None = None
        if probability >= accept_threshold and endpoint_used:
            decision, reason = "rejected", "one_to_one_conflict"
        elif probability >= accept_threshold and competing:
            decision, reason = "review", "multiple_candidates_above_accept"
        elif probability >= accept_threshold:
            decision = "accepted"
            used_baseline.add(baseline_id)
            used_endline.add(endline_id)
        elif probability >= review_floor:
            decision, reason = "review", "score_between_review_floor_and_accept"
        else:
            decision = "rejected"

        transferred = str(item["baseline_school_id"]) != str(item["endline_school_id"])
        if transferred and decision == "accepted":
            reason = "school_transfer_detected"
        rows.append(
            {
                "link_id": stable_id("link", baseline_id, endline_id),
                "baseline_record_id": baseline_id,
                "endline_record_id": endline_id,
                "school_id": item["school_id"],
                "method": "combined",
                "match_probability": probability,
                "decision": decision,
                "review_reason": reason,
                "transferred_flag": transferred,
                "source_method": item["method"],
                "pass_id": item["pass_id"],
            }
        )

    result = typed_frame(rows, RESULT_COLUMNS)
    accepted = result.loc[result["decision"] == "accepted"]
    if accepted["baseline_record_id"].duplicated().any():
        raise AssertionError("Accepted results contain duplicate baseline IDs")
    if accepted["endline_record_id"].duplicated().any():
        raise AssertionError("Accepted results contain duplicate endline IDs")
    return result
