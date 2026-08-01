"""Pick one-to-one links from exact and Splink pairs."""

from __future__ import annotations

import pandas as pd

from sbfp_platform.linkage._frames import RESULT_COLUMNS, typed_frame
from sbfp_platform.utils.hashing import stable_id


def _collapse_pairs(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    if "ambiguous" not in candidates:
        candidates = candidates.assign(ambiguous=False)
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
    candidates: pd.DataFrame,
    *,
    accept_threshold: float,
    review_floor: float,
    ambiguity_margin_weight: float = 1.0,
) -> pd.DataFrame:
    """Accept clear mutual-best links and route close alternatives to review."""
    if not 0 <= review_floor <= accept_threshold <= 1:
        raise ValueError("Expected 0 <= review_floor <= accept_threshold <= 1")
    if ambiguity_margin_weight < 0:
        raise ValueError("ambiguity_margin_weight must be non-negative")
    pairs = _collapse_pairs(candidates)
    if pairs.empty:
        return typed_frame([], RESULT_COLUMNS)

    above_accept = pairs.loc[pairs["match_probability"] >= accept_threshold].copy()
    if not above_accept.empty:
        above_accept["_baseline_rank"] = above_accept.groupby("baseline_record_id")[
            "match_weight"
        ].rank(method="min", ascending=False)
        above_accept["_endline_rank"] = above_accept.groupby("endline_record_id")[
            "match_weight"
        ].rank(method="min", ascending=False)

        def second_best(values: pd.Series) -> float:
            ordered = values.sort_values(ascending=False)
            return float(ordered.iloc[1]) if len(ordered) > 1 else float("-inf")

        baseline_second = above_accept.groupby("baseline_record_id")["match_weight"].transform(
            second_best
        )
        endline_second = above_accept.groupby("endline_record_id")["match_weight"].transform(
            second_best
        )
        above_accept["_margin"] = pd.concat(
            [
                above_accept["match_weight"] - baseline_second,
                above_accept["match_weight"] - endline_second,
            ],
            axis=1,
        ).min(axis=1)
        clear_ids = set(
            above_accept.loc[
                above_accept["_baseline_rank"].eq(1)
                & above_accept["_endline_rank"].eq(1)
                & above_accept["_margin"].gt(ambiguity_margin_weight)
                & ~above_accept["ambiguous"],
                "candidate_id",
            ].astype(str)
        )
    else:
        clear_ids = set()

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
        clear_winner = str(item["candidate_id"]) in clear_ids
        reason: str | None = None
        if probability >= accept_threshold and endpoint_used:
            decision, reason = "rejected", "one_to_one_conflict"
        elif probability >= accept_threshold and clear_winner:
            decision = "accepted"
            used_baseline.add(baseline_id)
            used_endline.add(endline_id)
        elif probability >= accept_threshold:
            decision, reason = "review", "ambiguous_candidate_margin"
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
                "method": str(item["method"]),
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
