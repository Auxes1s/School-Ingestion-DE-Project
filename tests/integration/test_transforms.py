from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pandas as pd
import pytest

from sbfp_platform.config import load_config
from sbfp_platform.contracts import FORBIDDEN_GOLD_COLUMNS
from sbfp_platform.transforms.run import build_exports, build_gold, build_silver


def _config(tmp_path):
    base = load_config("tiny")
    lakehouse = tmp_path / "lakehouse"
    paths = replace(
        base.paths,
        lakehouse_dir=lakehouse,
        bronze_dir=lakehouse / "bronze",
        silver_dir=lakehouse / "silver",
        gold_dir=lakehouse / "gold",
        linkage_dir=lakehouse / "linkage",
        duckdb_path=lakehouse / "platform.duckdb",
        outputs_dir=tmp_path / "outputs",
        exports_dir=tmp_path / "outputs" / "exports",
        reports_dir=tmp_path / "outputs" / "reports",
    )
    return replace(base, paths=paths)


def _metadata(record_id: str, period: str | None = None) -> dict:
    return {
        "run_id": "ingest_test",
        "source_file_id": "file-1",
        "source_file_path": "synthetic.xlsx",
        "source_sheet_name": "Sheet1",
        "source_row_number": 1,
        "file_hash": "abc",
        "ingested_at": datetime(2026, 1, 1),
        "raw_payload_json": "{}",
        "record_id": record_id,
        "dataset": "school_submission",
        "period_guess": period,
        "school_id_guess": None,
        "source_header_row": 0,
    }


def _write_bronze(config) -> None:
    bronze = config.paths.bronze_dir
    submissions = []
    for record_id, period, measured, height, weight in (
        ("baseline-1", "baseline", "2024-09-01", "120", "24"),
        ("endline-1", "endline", "2025-04-01", "124", "26"),
    ):
        submissions.append(
            {
                "school_name": "Test Elementary School",
                "school_id": "100001",
                "lrn_clean": "1234-5678-9012",
                "student_name_clean": "Dela Cruz, Ana",
                "birthday_str": "2016-01-01",
                "birthday_str_parsed": pd.Timestamp("2016-01-01"),
                "birthday_str_parse_rule": "iso",
                "birthday_str_parse_confidence": 1.0,
                "birthday_str_issue_flag": None,
                "sex": "Female",
                "grade": "Grade 3",
                "height_cm": height,
                "weight_kg": weight,
                "measurement_date": measured,
                "measurement_date_parsed": pd.Timestamp(measured),
                "measurement_date_parse_rule": "iso",
                "measurement_date_parse_confidence": 1.0,
                "measurement_date_issue_flag": None,
                **_metadata(record_id, period),
            }
        )

    school = {
        "school_id": "100001",
        "school_name": "Test Elementary School",
        "division": "Test Division",
        "municipality": "Test Town",
        "barangay": "Test Barangay",
        "urban_rural": "Rural",
        "treatment_status": "1",
        "matched_pair_id": "PAIR-1",
        **_metadata("school-1"),
    }
    enrollment = {
        "school_name": "Test Elementary School",
        "school_year": "2024-2025",
        "current_enrollment": "120",
        **_metadata("enrollment-1"),
    }
    allocation = {
        "school_name": "Test Elementary School",
        "school_year": "2024-2025",
        "allocated_children": "100",
        "delivery_tranche_count": "2",
        **_metadata("allocation-1"),
    }
    for table, rows in (
        ("school_submissions", submissions),
        ("school_masterlist", [school]),
        ("enrollment_snapshots", [enrollment]),
        ("program_allocations", [allocation]),
    ):
        target = bronze / table
        target.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(target / "part.parquet", index=False)


def _write_gold_inputs(config) -> None:
    pd.DataFrame(
        [
            {
                "issue_id": "issue-1",
                "run_id": "dqa-test",
                "rule_id": "DQA_RANGE_IMPLAUSIBLE_HEIGHT",
                "severity": "LOW",
                "scope": "record",
                "source_file_id": "file-1",
                "school_id": "100001",
                "period": "baseline",
                "record_id": "baseline-1",
                "field_name": "height_cm",
                "observed_value": "120",
                "issue_message": "test issue",
                "suggested_action": None,
                "resolved_status": "unresolved",
                "detected_at": datetime(2026, 1, 1),
            }
        ]
    ).to_parquet(config.paths.silver_dir / "silver_dqa_issues.parquet", index=False)
    config.paths.linkage_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "link_id": "link-1",
                "baseline_record_id": "baseline-1",
                "endline_record_id": "endline-1",
                "school_id": "100001",
                "method": "deterministic",
                "match_probability": 1.0,
                "decision": "accepted",
                "review_reason": None,
                "transferred_flag": False,
            }
        ]
    ).to_parquet(config.paths.linkage_dir / "silver_linkage_results.parquet", index=False)
    pd.DataFrame(
        [
            {
                "candidate_id": "candidate-1",
                "baseline_record_id": "baseline-1",
                "endline_record_id": "endline-1",
                "school_id": "100001",
                "method": "deterministic",
                "pass_id": "exact_lrn",
                "match_probability": 1.0,
                "match_weight": 10.0,
            }
        ]
    ).to_parquet(config.paths.linkage_dir / "silver_linkage_candidates.parquet", index=False)


@pytest.mark.integration
def test_dbt_silver_gold_and_exports_are_ordered_and_privacy_safe(tmp_path) -> None:
    config = _config(tmp_path)
    _write_bronze(config)

    silver = build_silver(config)
    assert set(silver.models) == {
        "silver_child_records",
        "silver_measurements",
        "silver_schools",
        "silver_allocations",
    }
    children = pd.read_parquet(config.paths.silver_dir / "silver_child_records.parquet")
    assert children["lrn_clean"].tolist() == ["123456789012", "123456789012"]

    _write_gold_inputs(config)
    gold = build_gold(config)
    panel = pd.read_parquet(config.paths.gold_dir / "gold_evaluation_child_panel.parquet")
    assert len(panel) == 1
    assert panel.loc[0, "elapsed_days"] == 212.0
    assert not (set(panel.columns) & set(FORBIDDEN_GOLD_COLUMNS))
    assert len(gold.models) == 6

    exports = build_exports(config)
    assert len(exports.parquet_paths) == 13
    assert (config.paths.exports_dir / "evaluation_child_panel.csv").is_file()
    assert (config.paths.exports_dir / "evaluation_child_panel.parquet").is_file()
    assert (config.paths.exports_dir / "data_dictionary.csv").is_file()
