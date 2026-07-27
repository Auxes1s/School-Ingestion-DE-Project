"""Fixed-seed quality floors for the tiny public demo."""

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


def test_combined_linkage_regression_floor() -> None:
    score = _scorecard("gold_linkage_scorecard")
    operating = score[(score["method"] == "combined") & (score["threshold"] == 0.75)].iloc[0]
    assert operating["precision"] >= 0.98
    assert operating["recall"] >= 0.90
    assert operating["f1"] >= 0.94
    assert operating["transfer_recall"] >= 0.75
    assert operating["review_queue_size"] <= 150


def test_dqa_regression_floor() -> None:
    score = _scorecard("gold_dqa_scorecard").set_index("rule_id")
    targeted = score[score["injected_count"] > 0]
    weighted_detection = targeted["detected_count"].sum() / targeted["injected_count"].sum()
    assert weighted_detection >= 0.90
    assert score.loc["DQA_RANGE_IMPLAUSIBLE_HEIGHT", "detection_rate"] >= 0.95
    assert score.loc["DQA_RANGE_IMPLAUSIBLE_WEIGHT", "detection_rate"] >= 0.95
    assert score.loc["DQA_MEASUREMENT_DIGIT_HEAPING", "detection_rate"] >= 0.90
    assert score.loc["DQA_TIMELINESS_LATE_SUBMISSION", "detection_rate"] >= 0.90
