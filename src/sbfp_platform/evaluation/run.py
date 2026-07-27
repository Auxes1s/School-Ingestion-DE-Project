"""Build measured DQA and linkage scorecards against the synthetic answer key.

This is deliberately the only pipeline module that reads ``config.paths.ground_truth_dir``.
The evaluated pipeline never sees these tables; evaluation joins them to already-written
silver/linkage outputs after the pipeline has finished.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pandera.pandas import DataFrameSchema

from sbfp_platform.contracts import (
    GOLD_DQA_SCORECARD,
    GOLD_LINKAGE_SCORECARD,
    LINKAGE_CANDIDATES,
    LINKAGE_RESULTS,
    SILVER_CHILD_RECORDS,
    SILVER_DQA_ISSUES,
    TRUTH_CHILDREN,
    TRUTH_DEFECTS,
    TRUTH_LINKS,
)
from sbfp_platform.evaluation.reports import write_reports
from sbfp_platform.utils.logging import get_logger

logger = get_logger(__name__)

DQA_OUTPUT = "gold_dqa_scorecard.parquet"
LINKAGE_OUTPUT = "gold_linkage_scorecard.parquet"


class MissingEvaluationInputError(FileNotFoundError):
    """A required truth or pipeline output table is missing."""


def _read_table(directory: Path, table: str, schema: DataFrameSchema) -> pd.DataFrame:
    """Read and validate either a parquet file or a partitioned table directory."""
    single = directory / f"{table}.parquet"
    partitioned = directory / table
    paths: list[Path] = []
    if single.is_file():
        paths.append(single)
    if partitioned.is_dir():
        paths.extend(sorted(partitioned.rglob("*.parquet")))
    if not paths:
        raise MissingEvaluationInputError(
            f"Required evaluation input {table!r} was not found under {directory}."
        )
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    return schema.validate(frame, lazy=True)


def _safe_ratio(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else float("nan")


def build_dqa_scorecard(
    defects: pd.DataFrame,
    issues: pd.DataFrame,
    config: Any,
    child_records: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Score each configured rule at the observable ``(record_id, rule_id)`` grain.

    Only defects marked ``expected_detectable`` enter the recall denominator. A raised
    issue is a true detection exactly when its record/rule pair is expected; every other
    distinct raised pair is a false positive. Duplicate issue rows cannot inflate either
    count.
    """
    detectable = defects.loc[defects["expected_detectable"]].copy()
    detectable["rule_id"] = detectable["defect_type"].map(config.rule_for_defect)
    unmapped = sorted(detectable.loc[detectable["rule_id"].isna(), "defect_type"].unique())
    if unmapped:
        raise ValueError(
            "Detectable truth defects have no configured DQA rule mapping: " + ", ".join(unmapped)
        )

    issue_keys = issues.copy()
    if "source_file_id" not in issue_keys:
        issue_keys["source_file_id"] = None
    issue_keys["evaluation_id"] = issue_keys["record_id"].fillna(issue_keys["source_file_id"])
    detected_pairs = (
        issue_keys[["evaluation_id", "rule_id"]]
        .drop_duplicates()
        .rename(columns={"evaluation_id": "record_id"})
    )
    expected_pairs = detectable[["record_id", "rule_id"]].drop_duplicates()
    pair_hits = expected_pairs.merge(detected_pairs, on=["record_id", "rule_id"], how="inner")

    rows: list[dict[str, object]] = []
    for rule in config.dqa_rules:
        rule_id = rule["rule_id"]
        rule_defects = detectable.loc[detectable["rule_id"] == rule_id]
        injected = len(rule_defects)

        if rule.get("scope") == "school_period" and child_records is not None:
            detected, false_positives = _score_school_period_rule(
                rule_id, rule_defects, issue_keys, child_records
            )
            rows.append(
                {
                    "rule_id": rule_id,
                    "severity": rule["severity"],
                    "injected_count": int(injected),
                    "detected_count": detected,
                    "missed_count": int(injected - detected),
                    "false_positive_count": false_positives,
                    "detection_rate": _safe_ratio(detected, injected),
                    "precision": _safe_ratio(detected, detected + false_positives),
                }
            )
            continue

        hit_records = set(pair_hits.loc[pair_hits["rule_id"] == rule_id, "record_id"])
        # A rule emits at record/rule grain. If two truth rows describe the same targeted
        # corruption, the one issue is evidence for both injected defect rows.
        detected = int(rule_defects["record_id"].isin(hit_records).sum())
        raised = detected_pairs.loc[detected_pairs["rule_id"] == rule_id]
        expected = expected_pairs.loc[expected_pairs["rule_id"] == rule_id]
        false_positives = len(
            raised.merge(expected, on=["record_id", "rule_id"], how="left", indicator=True).loc[
                lambda frame: frame["_merge"] == "left_only"
            ]
        )

        rows.append(
            {
                "rule_id": rule_id,
                "severity": rule["severity"],
                "injected_count": int(injected),
                "detected_count": detected,
                "missed_count": int(injected - detected),
                "false_positive_count": int(false_positives),
                "detection_rate": _safe_ratio(detected, injected),
                "precision": _safe_ratio(detected, detected + false_positives),
            }
        )

    configured = {rule["rule_id"] for rule in config.dqa_rules}
    unknown = sorted(set(detected_pairs["rule_id"]) - configured)
    if unknown:
        raise ValueError("DQA issues contain unconfigured rule_id values: " + ", ".join(unknown))

    return GOLD_DQA_SCORECARD.validate(pd.DataFrame(rows), lazy=True)


def _score_school_period_rule(
    rule_id: str,
    rule_defects: pd.DataFrame,
    issues: pd.DataFrame,
    child_records: pd.DataFrame,
) -> tuple[int, int]:
    """Score aggregate rules at the group they can actually observe.

    The generator records every altered measurement, while digit-heaping is detectable
    only as a school-period distribution. A defect is therefore detected when its
    record belongs to a flagged group. A false positive is a flagged group containing no
    injected defect; this avoids pretending the aggregate rule identifies individual
    rows inside a flagged distribution.
    """
    identity = child_records[["child_record_id", "school_id", "period"]].drop_duplicates()
    truth_groups = rule_defects.merge(
        identity, left_on="record_id", right_on="child_record_id", how="left"
    )
    flagged = issues.loc[issues["rule_id"].eq(rule_id), ["school_id", "period"]].drop_duplicates()
    detected = int(truth_groups.merge(flagged, on=["school_id", "period"], how="inner").shape[0])
    injected_groups = truth_groups[["school_id", "period"]].dropna().drop_duplicates()
    false_positives = int(
        flagged.merge(injected_groups, on=["school_id", "period"], how="left", indicator=True)
        .loc[lambda frame: frame["_merge"] == "left_only"]
        .shape[0]
    )
    return detected, false_positives


def _pairs(frame: pd.DataFrame) -> set[tuple[str, str]]:
    return set(zip(frame["baseline_record_id"], frame["endline_record_id"], strict=False))


def _probability(frame: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(frame["match_probability"], errors="coerce")


def _resolve_method_candidates(
    candidates: pd.DataFrame, method: str, threshold: float, review_floor: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply a deterministic one-to-one policy to one raw candidate method.

    Candidate tables deliberately retain competing pairs. Scoring them all would inflate
    false positives and could make match rate exceed one. At each threshold we collapse
    duplicate pairs, accept only pairs with no competing baseline or endline endpoint,
    and route both competition and gray-zone scores to review.
    """
    method_rows = candidates.loc[candidates["method"] == method].copy()
    if method_rows.empty:
        return method_rows, method_rows

    probability = _probability(method_rows)
    if method == "deterministic":
        probability = probability.fillna(1.0)
    method_rows["_probability"] = probability
    method_rows["_weight"] = pd.to_numeric(method_rows["match_weight"], errors="coerce")
    method_rows = (
        method_rows.sort_values(
            ["_probability", "_weight", "candidate_id"],
            ascending=[False, False, True],
            kind="stable",
        )
        .drop_duplicates(["baseline_record_id", "endline_record_id"], keep="first")
        .copy()
    )
    eligible = method_rows.loc[method_rows["_probability"] >= threshold].copy()
    baseline_counts = eligible["baseline_record_id"].value_counts()
    endline_counts = eligible["endline_record_id"].value_counts()
    competing = eligible["baseline_record_id"].map(baseline_counts).gt(1) | eligible[
        "endline_record_id"
    ].map(endline_counts).gt(1)
    predicted = eligible.loc[~competing]
    gray = method_rows.loc[
        method_rows["_probability"].ge(review_floor) & method_rows["_probability"].lt(threshold)
    ]
    review = pd.concat([eligible.loc[competing], gray], ignore_index=True)
    return predicted, review


def _predictions_for_method(
    method: str,
    threshold: float,
    candidates: pd.DataFrame,
    results: pd.DataFrame,
    review_floor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return predicted and review pairs under one method/threshold policy.

    Raw deterministic and Splink methods are evaluated from their candidate outputs.
    Combined is different: it is the resolver's globally one-to-one output, so only
    explicit ``accepted`` decisions may become predictions. Raising the threshold can
    demote a probabilistic accepted pair to review, but lowering it never promotes an
    unresolved or rejected decision to an accepted match.
    """
    if method in {"deterministic", "splink"}:
        return _resolve_method_candidates(candidates, method, threshold, review_floor)

    probability = _probability(results)
    accepted = results["decision"].eq("accepted")
    score_passes = probability.isna() | probability.ge(threshold)
    predicted = results.loc[accepted & score_passes]

    unresolved_review = results["decision"].eq("review") & (
        probability.isna() | probability.ge(review_floor)
    )
    demoted_to_review = accepted & probability.ge(review_floor) & probability.lt(threshold)
    review = results.loc[unresolved_review | demoted_to_review]
    return predicted, review


def build_linkage_scorecard(
    children: pd.DataFrame,
    truth_links: pd.DataFrame,
    candidates: pd.DataFrame,
    results: pd.DataFrame,
    config: Any,
) -> pd.DataFrame:
    """Compute precision/recall/F1 and operational metrics over the configured sweep."""
    truth_pairs = _pairs(truth_links)
    transfer_pairs = _pairs(truth_links.loc[truth_links["transferred"]])
    baseline_count = len(children)
    sweep = [float(value) for value in config.linkage["probabilistic"]["sweep"]]
    review_floor = float(config.linkage["probabilistic"]["review_floor"])

    rows: list[dict[str, object]] = []
    for method in ("deterministic", "splink", "combined"):
        for threshold in sweep:
            predicted, review = _predictions_for_method(
                method, threshold, candidates, results, review_floor
            )
            predicted_pairs = _pairs(predicted)
            true_positives = len(predicted_pairs & truth_pairs)
            false_positives = len(predicted_pairs - truth_pairs)
            false_negatives = len(truth_pairs - predicted_pairs)
            precision = _safe_ratio(true_positives, true_positives + false_positives)
            recall = _safe_ratio(true_positives, len(truth_pairs))
            f1 = (
                2 * precision * recall / (precision + recall)
                if pd.notna(precision) and pd.notna(recall) and precision + recall
                else float("nan")
            )
            # Candidate sets may contain competing endline choices. Coverage of unique
            # baseline records is therefore the honest bounded version of match rate.
            matched_baselines = predicted["baseline_record_id"].nunique()

            rows.append(
                {
                    "method": method,
                    "threshold": threshold,
                    "true_positives": int(true_positives),
                    "false_positives": int(false_positives),
                    "false_negatives": int(false_negatives),
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "match_rate": _safe_ratio(int(matched_baselines), baseline_count),
                    "review_queue_size": int(len(_pairs(review))),
                    "transfer_recall": _safe_ratio(
                        len(predicted_pairs & transfer_pairs), len(transfer_pairs)
                    ),
                }
            )

    return GOLD_LINKAGE_SCORECARD.validate(pd.DataFrame(rows), lazy=True)


def _write_scorecard(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def build_scorecards(config: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load, validate, score, and materialize both gold evaluation scorecards."""
    truth_dir = config.paths.ground_truth_dir
    children = _read_table(truth_dir, "truth_children", TRUTH_CHILDREN)
    links = _read_table(truth_dir, "truth_links", TRUTH_LINKS)
    defects = _read_table(truth_dir, "truth_defects", TRUTH_DEFECTS)
    issues = _read_table(config.paths.silver_dir, "silver_dqa_issues", SILVER_DQA_ISSUES)
    child_records = _read_table(
        config.paths.silver_dir, "silver_child_records", SILVER_CHILD_RECORDS
    )
    candidates = _read_table(
        config.paths.linkage_dir, "silver_linkage_candidates", LINKAGE_CANDIDATES
    )
    results = _read_table(config.paths.linkage_dir, "silver_linkage_results", LINKAGE_RESULTS)

    dqa = build_dqa_scorecard(defects, issues, config, child_records)
    linkage = build_linkage_scorecard(children, links, candidates, results, config)

    dqa_path = config.paths.gold_dir / DQA_OUTPUT
    linkage_path = config.paths.gold_dir / LINKAGE_OUTPUT
    _write_scorecard(dqa, dqa_path)
    _write_scorecard(linkage, linkage_path)
    reports = write_reports(config, dqa, linkage, child_records)
    logger.info("DQA scorecard written to %s", dqa_path)
    logger.info("Linkage scorecard written to %s", linkage_path)
    logger.info("Wrote %d HTML reports to %s", len(reports), config.paths.reports_dir)
    return dqa, linkage
