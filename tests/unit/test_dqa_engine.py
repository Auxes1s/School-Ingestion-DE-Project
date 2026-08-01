"""The engine: contract fit, row types, purity, and the entry point. This keeps the test fair."""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from sbfp_platform.config import load_config
from sbfp_platform.contracts import SILVER_DQA_ISSUES
from sbfp_platform.validation.engine import ISSUE_COLUMNS, evaluate
from sbfp_platform.validation.frames import MissingSilverError, load_frames
from sbfp_platform.validation.issues import RECORD_SCOPES
from sbfp_platform.validation.registry import RuleRegistryError
from sbfp_platform.validation.rules.quality import MIN_GROUP_SIZE
from sbfp_platform.validation.run import ISSUE_TABLE, issues_path, run_dqa
from tests.fixtures import dqa_frames as fx


@pytest.fixture(scope="module")
def cfg():
    return load_config(profile="tiny")


@pytest.fixture
def clean_lakehouse():
    """A lakehouse with nothing wrong with it. Every rule must stay silent."""
    records = fx.child_records(
        [
            {
                "child_record_id": f"CR{i:04d}",
                "lrn_clean": f"{100000000000 + i:012d}",
                "period": "baseline" if i % 2 else "endline",
                "raw_payload_json": fx.payload(
                    school_name="Bubong Central Elementary School",
                    birthday_str="2015-03-04",
                    measurement_date="2024-09-01",
                ),
            }
            for i in range(1, 11)
        ]
    )
    return {
        "child_records": records,
        "measurements": fx.measurements(
            [
                {
                    "measurement_id": f"MS{i:04d}",
                    "child_record_id": f"CR{i:04d}",
                    "period": "baseline" if i % 2 else "endline",
                    "height_cm": 120.0 + i + 0.3,
                    "weight_kg": 20.0 + i + 0.4,
                }
                for i in range(1, 11)
            ]
        ),
        "schools": fx.schools(),
        "allocations": fx.allocations(),
        "file_manifest": fx.file_manifest([{"modified_at": pd.Timestamp("2024-09-20")}]),
        "schema_drift": fx.schema_drift([{"drift_type": "unmapped_column"}]),
    }


@pytest.fixture
def messy_lakehouse(clean_lakehouse):
    """The clean lakehouse plus one defect of several kinds."""
    records = pd.concat(
        [
            clean_lakehouse["child_records"],
            fx.child_records(
                [
                    {
                        "child_record_id": "CR9001",
                        "lrn_clean": None,
                        "source_row_number": 91,
                    },
                    {
                        "child_record_id": "CR9002",
                        "lrn_clean": "12345",
                        "source_row_number": 92,
                    },
                    {
                        "child_record_id": "CR9003",
                        "birthday_str": None,
                        "lrn_clean": "100000009003",
                        "source_row_number": 93,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    measurements = pd.concat(
        [
            clean_lakehouse["measurements"],
            fx.measurements(
                [
                    {
                        "measurement_id": "MS9001",
                        "child_record_id": "CR9001",
                        "height_cm": 260.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    heaped = fx.measurements(
        [
            {
                "measurement_id": f"MSH{i:04d}",
                "child_record_id": f"CRH{i:04d}",
                "school_id": "SCH_009",
                "period": "endline",
                "height_cm": 120.0 + 5 * (i % 4),
            }
            for i in range(MIN_GROUP_SIZE)
        ]
    )
    return {
        **clean_lakehouse,
        "child_records": records,
        "measurements": pd.concat([measurements, heaped], ignore_index=True),
        "allocations": fx.allocations([{"allocated_children": 300.0, "current_enrollment": 400.0}]),
    }


def test_output_conforms_to_the_issue_contract(messy_lakehouse, cfg) -> None:
    issues, _ = evaluate(messy_lakehouse, cfg)
    SILVER_DQA_ISSUES.validate(issues)
    assert list(issues.columns) == list(ISSUE_COLUMNS)
    assert issues["issue_id"].is_unique
    assert (issues["resolved_status"] == "unresolved").all()
    assert issues["run_id"].nunique() == 1


def test_a_clean_lakehouse_produces_no_issues(clean_lakehouse, cfg) -> None:
    """The engine-level false-positive test. This keeps the test fair. It must work as shown."""
    issues, outcomes = evaluate(clean_lakehouse, cfg)
    firing = {outcome.rule_id: outcome.issue_count for outcome in outcomes if outcome.issue_count}
    assert firing == {}, f"Rules fired on clean data: {firing}"
    assert issues.empty
    SILVER_DQA_ISSUES.validate(issues)


def test_severity_and_scope_are_taken_from_the_config(messy_lakehouse, cfg) -> None:
    declared = {raw["rule_id"]: (raw["severity"], raw["scope"]) for raw in cfg.dqa_rules}
    issues, _ = evaluate(messy_lakehouse, cfg)
    observed = {
        row["rule_id"]: (row["severity"], row["scope"]) for row in issues.to_dict("records")
    }
    assert observed
    for rule_id, pair in observed.items():
        assert pair == declared[rule_id]


def test_record_scope_issues_carry_a_record_id_and_others_do_not(messy_lakehouse, cfg) -> None:
    """Record_id is the join key to truth_defects. getting it wrong reads as a zero detection rate rather than as a bug."""
    issues, _ = evaluate(messy_lakehouse, cfg)
    known_ids = set(messy_lakehouse["child_records"]["child_record_id"]) | set(
        messy_lakehouse["measurements"]["child_record_id"]
    )

    record_scoped = issues[issues["scope"].isin(RECORD_SCOPES)]
    assert not record_scoped.empty
    assert record_scoped["record_id"].notna().all()
    assert set(record_scoped["record_id"]) <= known_ids

    aggregate = issues[~issues["scope"].isin(RECORD_SCOPES)]
    assert aggregate["record_id"].isna().all()
    assert aggregate[["source_file_id", "school_id"]].notna().any(axis=1).all(), (
        "A file/school/school_period issue with no identifier cannot be acted on."
    )


def test_rules_do_not_mutate_their_inputs(messy_lakehouse, cfg) -> None:
    """Purity is the design constraint that makes the rules testable in on its own."""
    before = {name: frame.copy(deep=True) for name, frame in messy_lakehouse.items()}
    evaluate(messy_lakehouse, cfg)
    for name, frame in messy_lakehouse.items():
        pd.testing.assert_frame_equal(frame, before[name])


def test_missing_optional_frames_skip_rules_rather_than_crash(messy_lakehouse, cfg) -> None:
    minimal = {
        "child_records": messy_lakehouse["child_records"],
        "measurements": messy_lakehouse["measurements"],
    }
    issues, outcomes = evaluate(minimal, cfg)
    skipped = {outcome.rule_id for outcome in outcomes if not outcome.ran}
    assert skipped == {
        "DQA_SCHEMA_REQUIRED_COLUMN_MISSING",
        "DQA_REFERENCE_SCHOOL_NAME_DRIFT",
        "DQA_TIMELINESS_LATE_SUBMISSION",
        "DQA_PROGRAM_ENROLLMENT_EXCEEDS_ALLOCATION",
    }
    assert not issues.empty
    assert set(issues["rule_id"]) & skipped == set()


def test_every_configured_rule_reports_an_outcome(messy_lakehouse, cfg) -> None:
    _, outcomes = evaluate(messy_lakehouse, cfg)
    assert [outcome.rule_id for outcome in outcomes] == [raw["rule_id"] for raw in cfg.dqa_rules]


def test_evaluate_refuses_to_run_with_a_mismatched_registry(messy_lakehouse, cfg) -> None:
    broken = dataclasses.replace(
        cfg, dqa=({**cfg.dqa, "rules": [*cfg.dqa_rules, {"rule_id": "DQA_PHANTOM"}]})
    )
    with pytest.raises(RuleRegistryError, match="DQA_PHANTOM"):
        evaluate(messy_lakehouse, broken)


# --------------------------------------------------------------------------------------
# run_dqa
# --------------------------------------------------------------------------------------


def _config_at(cfg, root):
    """The real config with its lakehouse pointed at a temporary folder. This keeps the test fair. It must work as shown."""
    paths = dataclasses.replace(cfg.paths, silver_dir=root / "silver", bronze_dir=root / "bronze")
    return dataclasses.replace(cfg, paths=paths)


def test_run_dqa_explains_what_to_run_when_silver_is_missing(cfg, tmp_path) -> None:
    with pytest.raises(MissingSilverError) as excinfo:
        run_dqa(_config_at(cfg, tmp_path))
    message = str(excinfo.value)
    assert "silver_child_records" in message
    assert "build-silver" in message


def test_run_dqa_writes_the_issue_registry(cfg, tmp_path, messy_lakehouse) -> None:
    scoped = _config_at(cfg, tmp_path)
    (tmp_path / "silver").mkdir()
    (tmp_path / "bronze").mkdir()
    for name, table in (
        ("child_records", "silver_child_records"),
        ("measurements", "silver_measurements"),
        ("schools", "silver_schools"),
        ("allocations", "silver_allocations"),
    ):
        messy_lakehouse[name].to_parquet(tmp_path / "silver" / f"{table}.parquet", index=False)
    for name, table in (
        ("file_manifest", "bronze_file_manifest"),
        ("schema_drift", "bronze_schema_drift_log"),
    ):
        messy_lakehouse[name].to_parquet(tmp_path / "bronze" / f"{table}.parquet", index=False)

    issues = run_dqa(scoped)
    written = pd.read_parquet(issues_path(scoped))

    assert issues_path(scoped).name == f"{ISSUE_TABLE}.parquet"
    assert len(written) == len(issues)
    SILVER_DQA_ISSUES.validate(written)
    assert set(load_frames(scoped)) >= {"child_records", "measurements"}


def test_load_frames_accepts_physical_bronze_metadata_names(cfg, tmp_path, messy_lakehouse) -> None:
    scoped = _config_at(cfg, tmp_path)
    (tmp_path / "silver").mkdir()
    for name, table in (
        ("child_records", "silver_child_records"),
        ("measurements", "silver_measurements"),
    ):
        messy_lakehouse[name].to_parquet(tmp_path / "silver" / f"{table}.parquet", index=False)
    for name, table, part in (
        ("file_manifest", "file_manifest", "manifest"),
        ("schema_drift", "schema_drift_log", "run"),
    ):
        directory = tmp_path / "bronze" / table
        directory.mkdir(parents=True)
        messy_lakehouse[name].to_parquet(directory / f"{part}.parquet", index=False)

    frames = load_frames(scoped)
    assert {"file_manifest", "schema_drift"} <= set(frames)
