"""Fixed-seed quality floors for the tiny public demo. This keeps the test fair. It must work as shown."""

from __future__ import annotations

import pandas as pd
import pytest

from sbfp_platform.config import load_config

pytestmark = pytest.mark.integration


def _scorecard(name: str) -> pd.DataFrame:
    path = load_config(profile="tiny", seed=2026).paths.gold_dir / f"{name}.parquet"
    if not path.is_file():
        pytest.skip("Run the tiny full-refresh before scorecard regression tests.")
    return pd.read_parquet(path)


def test_trained_splink_linkage_regression_floor() -> None:
    score = _scorecard("gold_linkage_scorecard")
    operating = score[(score["method"] == "splink") & (score["threshold"] == 0.10)].iloc[0]
    deterministic = score[(score["method"] == "deterministic") & (score["threshold"] == 0.10)].iloc[
        0
    ]
    assert operating["precision"] == 1.0
    assert operating["recall"] >= 0.92
    assert operating["f1"] >= 0.95
    assert operating["transfer_recall"] >= 0.70
    assert operating["review_queue_size"] <= 75
    assert deterministic["recall"] <= 0.75
    assert operating["recall"] - deterministic["recall"] >= 0.28


def test_scorecard_contains_only_benchmark_and_trained_splink() -> None:
    score = _scorecard("gold_linkage_scorecard")
    assert set(score["method"]) == {"deterministic", "splink"}


def test_dqa_regression_floor() -> None:
    score = _scorecard("gold_dqa_scorecard").set_index("rule_id")
    targeted = score[score["injected_count"] > 0]
    weighted_detection = targeted["detected_count"].sum() / targeted["injected_count"].sum()
    assert weighted_detection >= 0.90
    assert score.loc["DQA_RANGE_IMPLAUSIBLE_HEIGHT", "detection_rate"] >= 0.95
    assert score.loc["DQA_RANGE_IMPLAUSIBLE_WEIGHT", "detection_rate"] >= 0.95
    assert score.loc["DQA_MEASUREMENT_DIGIT_HEAPING", "detection_rate"] >= 0.90
    assert score.loc["DQA_TIMELINESS_LATE_SUBMISSION", "detection_rate"] >= 0.90
