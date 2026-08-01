"""Focused tests for honest known truth scorecard accounting. This keeps the test fair."""

from __future__ import annotations

import pandas as pd
import pytest

from sbfp_platform.evaluation.run import build_dqa_scorecard, build_linkage_scorecard


class ScorecardConfig:
    dqa_rules = [
        {"rule_id": "RULE_A", "severity": "HIGH", "detects": ["defect_a"]},
        {"rule_id": "RULE_B", "severity": "LOW", "detects": []},
    ]
    linkage = {
        "probabilistic": {
            "review_floor": 0.65,
            "ambiguity_margin_weight": 1.0,
            "sweep": [0.65, 0.75, 0.85],
        }
    }

    def rule_for_defect(self, defect_type: str) -> str | None:
        return "RULE_A" if defect_type == "defect_a" else None


def test_dqa_counts_distinct_record_rule_hits_and_false_positives() -> None:
    defects = pd.DataFrame(
        [
            {"record_id": "r1", "defect_type": "defect_a", "expected_detectable": True},
            {"record_id": "r2", "defect_type": "defect_a", "expected_detectable": True},
            {"record_id": "r3", "defect_type": "not_targeted", "expected_detectable": False},
        ]
    )
    # A repeat of r1 must not raise the hit rate or trust score.
    # A hit on a flaw we do not seek is still a false hit for RULE_A.
    issues = pd.DataFrame(
        [
            {"record_id": "r1", "rule_id": "RULE_A"},
            {"record_id": "r1", "rule_id": "RULE_A"},
            {"record_id": "r3", "rule_id": "RULE_A"},
            {"record_id": None, "rule_id": "RULE_B"},
        ]
    )

    scorecard = build_dqa_scorecard(defects, issues, ScorecardConfig())
    rule_a = scorecard.set_index("rule_id").loc["RULE_A"]
    rule_b = scorecard.set_index("rule_id").loc["RULE_B"]

    assert rule_a["injected_count"] == 2
    assert rule_a["detected_count"] == 1
    assert rule_a["missed_count"] == 1
    assert rule_a["false_positive_count"] == 1
    assert rule_a["detection_rate"] == pytest.approx(0.5)
    assert rule_a["precision"] == pytest.approx(0.5)
    assert pd.isna(rule_b["detection_rate"])
    assert rule_b["false_positive_count"] == 1
    assert rule_b["precision"] == pytest.approx(0.0)


def test_dqa_rejects_detectable_defect_without_rule_mapping() -> None:
    defects = pd.DataFrame(
        [{"record_id": "r1", "defect_type": "unknown", "expected_detectable": True}]
    )
    issues = pd.DataFrame(columns=["record_id", "rule_id"])

    with pytest.raises(ValueError, match="no configured DQA rule mapping"):
        build_dqa_scorecard(defects, issues, ScorecardConfig())


def test_dqa_uses_source_file_identity_for_file_scoped_rules() -> None:
    class FileConfig(ScorecardConfig):
        dqa_rules = [
            {
                "rule_id": "RULE_A",
                "severity": "HIGH",
                "scope": "file",
                "detects": ["defect_a"],
            }
        ]

    defects = pd.DataFrame(
        [{"record_id": "file-1", "defect_type": "defect_a", "expected_detectable": True}]
    )
    issues = pd.DataFrame([{"record_id": None, "source_file_id": "file-1", "rule_id": "RULE_A"}])
    scorecard = build_dqa_scorecard(defects, issues, FileConfig())
    assert scorecard.iloc[0]["detected_count"] == 1
    assert scorecard.iloc[0]["detection_rate"] == pytest.approx(1.0)


def _linkage_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    children = pd.DataFrame({"true_child_id": ["c1", "c2", "c3"]})
    truth = pd.DataFrame(
        [
            {
                "baseline_record_id": "b1",
                "endline_record_id": "e1",
                "transferred": False,
            },
            {
                "baseline_record_id": "b2",
                "endline_record_id": "e2",
                "transferred": True,
            },
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "candidate_id": "d1",
                "baseline_record_id": "b1",
                "endline_record_id": "e1",
                "method": "deterministic",
                "match_probability": 1.0,
            },
            {
                "candidate_id": "d2",
                "baseline_record_id": "b1",
                "endline_record_id": "wrong",
                "method": "deterministic",
                "match_probability": 1.0,
            },
            {
                "candidate_id": "d3",
                "baseline_record_id": "b2",
                "endline_record_id": "e2",
                "method": "deterministic",
                "match_probability": 1.0,
            },
            {
                "candidate_id": "s1",
                "baseline_record_id": "b1",
                "endline_record_id": "e1",
                "method": "splink",
                "match_probability": 0.80,
            },
            {
                "candidate_id": "s2",
                "baseline_record_id": "b2",
                "endline_record_id": "e2",
                "method": "splink",
                "match_probability": 0.70,
            },
            {
                "candidate_id": "s3",
                "baseline_record_id": "b3",
                "endline_record_id": "wrong",
                "method": "splink",
                "match_probability": 0.90,
            },
        ]
    )
    candidates["match_weight"] = candidates["match_probability"] * 10
    candidates["school_id"] = "S1"
    candidates["pass_id"] = pd.NA
    candidates["baseline_school_id"] = "S1"
    candidates["endline_school_id"] = "S1"
    candidates["ambiguous"] = False
    results = pd.DataFrame(
        [
            {
                "baseline_record_id": "b1",
                "endline_record_id": "e1",
                "decision": "accepted",
                "match_probability": 0.80,
            },
            {
                "baseline_record_id": "b2",
                "endline_record_id": "e2",
                "decision": "review",
                "match_probability": 0.70,
            },
            {
                "baseline_record_id": "b3",
                "endline_record_id": "wrong",
                "decision": "rejected",
                "match_probability": 0.90,
            },
        ]
    )
    return children, truth, candidates, results


def test_linkage_sweep_compares_exact_benchmark_with_trained_splink() -> None:
    frames = _linkage_frames()
    scorecard = build_linkage_scorecard(*frames, ScorecardConfig())
    indexed = scorecard.set_index(["method", "threshold"])

    splink_low = indexed.loc[("splink", 0.65)]
    assert splink_low["true_positives"] == 2
    assert splink_low["false_positives"] == 1
    assert splink_low["recall"] == pytest.approx(1.0)
    assert splink_low["transfer_recall"] == pytest.approx(1.0)

    splink_operating = indexed.loc[("splink", 0.75)]
    assert splink_operating["true_positives"] == 1
    assert splink_operating["false_positives"] == 1
    assert splink_operating["review_queue_size"] == 1

    assert set(indexed.index.get_level_values("method")) == {"deterministic", "splink"}


def test_raw_method_resolution_does_not_score_competing_pairs_as_matches() -> None:
    frames = _linkage_frames()
    scorecard = build_linkage_scorecard(*frames, ScorecardConfig())
    deterministic = scorecard.loc[scorecard["method"] == "deterministic"]

    assert deterministic["match_rate"].tolist() == pytest.approx([1 / 3] * 3)
    assert (deterministic["true_positives"] == 1).all()
    assert (deterministic["false_positives"] == 0).all()
    assert (deterministic["review_queue_size"] == 2).all()
