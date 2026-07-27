from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sbfp_platform.config import load_config
from sbfp_platform.evaluation.reports import write_reports


def test_reports_are_written_without_identity_fields(tmp_path) -> None:
    base = load_config(profile="tiny")
    paths = replace(
        base.paths,
        reports_dir=tmp_path / "reports",
        gold_dir=tmp_path / "gold",
    )
    config = replace(base, paths=paths)
    paths.gold_dir.mkdir()
    pd.DataFrame(
        {
            "height_cm_baseline": [100.0],
            "height_cm_endline": [102.0],
            "weight_kg_baseline": [20.0],
            "weight_kg_endline": [21.0],
            "has_critical_issue": [False],
        }
    ).to_parquet(paths.gold_dir / "gold_evaluation_child_panel.parquet")
    dqa = pd.DataFrame(
        {"rule_id": ["R"], "injected_count": [1], "detected_count": [1], "detection_rate": [1.0]}
    )
    linkage = pd.DataFrame(
        {
            "method": ["combined"],
            "threshold": [0.75],
            "true_positives": [1],
            "false_positives": [0],
            "f1": [1.0],
        }
    )

    written = write_reports(config, dqa, linkage, pd.DataFrame(index=range(2)))
    assert {path.name for path in written} == {
        "data_quality_report.html",
        "pipeline_run_summary.html",
        "evaluation_readiness_report.html",
    }
    assert all("true_name" not in path.read_text(encoding="utf-8") for path in written)
