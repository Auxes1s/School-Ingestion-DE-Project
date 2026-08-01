"""Rules whose finding is about a file, a school, or a health check session."""

from __future__ import annotations

import pandas as pd

from sbfp_platform.validation.rules.quality import MIN_GROUP_SIZE
from tests.fixtures import dqa_frames as fx
from tests.fixtures.dqa_support import run_rule

HEAPING = "DQA_MEASUREMENT_DIGIT_HEAPING"
NAME_DRIFT = "DQA_REFERENCE_SCHOOL_NAME_DRIFT"
SCHEMA_MISSING = "DQA_SCHEMA_REQUIRED_COLUMN_MISSING"
LATE = "DQA_TIMELINESS_LATE_SUBMISSION"
DILUTION = "DQA_PROGRAM_ENROLLMENT_EXCEEDS_ALLOCATION"

MASTERLIST_NAME = "Bubong Central Elementary School"


# --------------------------------------------------------------------------------------
# Digit heaping
# --------------------------------------------------------------------------------------


def heights(values):
    return {"measurements": fx.measurements([{"height_cm": v} for v in values])}


def test_digit_heaping_fires_when_terminal_digits_cluster_on_zero_and_five() -> None:
    rounded = [120.0 + 5 * (i % 4) for i in range(MIN_GROUP_SIZE)]
    issues = run_rule(HEAPING, heights(rounded))
    assert len(issues) == 1
    assert issues[0].record_id is None
    assert (issues[0].school_id, issues[0].period) == (fx.SCHOOL_ID, "baseline")
    assert issues[0].field_name == "height_cm"


def test_digit_heaping_is_silent_on_evenly_spread_terminal_digits() -> None:
    spread = [120.0 + (i % 10) + 0.3 for i in range(MIN_GROUP_SIZE * 2)]
    assert run_rule(HEAPING, heights(spread)) == []


def test_digit_heaping_needs_enough_measurements_to_infer_anything() -> None:
    """Three terminal zeros out of five is noise, not a health check practice."""
    assert run_rule(HEAPING, heights([120.0, 125.0, 130.0, 121.3, 122.7])) == []


def test_digit_heaping_is_evaluated_per_school_period() -> None:
    clean = [{"height_cm": 120.0 + (i % 10) + 0.3, "period": "baseline"} for i in range(40)]
    heaped = [
        {
            "height_cm": 120.0 + 5 * (i % 4),
            "period": "endline",
            "school_id": "SCH_002",
        }
        for i in range(MIN_GROUP_SIZE)
    ]
    issues = run_rule(HEAPING, {"measurements": fx.measurements([*clean, *heaped])})
    assert [(issue.school_id, issue.period) for issue in issues] == [("SCH_002", "endline")]


# --------------------------------------------------------------------------------------
# School name drift
# --------------------------------------------------------------------------------------


def submission(name: str, **overrides):
    return {
        "child_records": fx.child_records(
            [{"raw_payload_json": fx.payload(school_name=name), **overrides}]
        ),
        "schools": fx.schools(),
    }


def test_school_name_drift_fires_on_any_departure_from_the_masterlist() -> None:
    issues = run_rule(NAME_DRIFT, submission("Bubong Central ES"))
    assert len(issues) == 1
    assert issues[0].record_id is None
    assert issues[0].source_file_id == fx.SOURCE_FILE_ID
    assert issues[0].school_id == fx.SCHOOL_ID
    assert issues[0].observed_value == "Bubong Central ES"


def test_school_name_drift_is_silent_on_an_exact_match() -> None:
    assert run_rule(NAME_DRIFT, submission(MASTERLIST_NAME)) == []


def test_school_name_drift_is_silent_when_the_school_is_not_in_the_masterlist() -> None:
    """An unknown school_id is a reference problem for the linkage layer, not a name drift finding, and guessing would produce a false positive per file. This keeps the test fair. It must work as shown."""
    frames = submission("Some Other School", school_id="SCH_999")
    assert run_rule(NAME_DRIFT, frames) == []


def test_school_name_drift_reports_one_issue_per_file_not_per_row() -> None:
    frames = {
        "child_records": fx.child_records(
            [{"raw_payload_json": fx.payload(school_name="Bubong Central ES")} for _ in range(5)]
        ),
        "schools": fx.schools(),
    }
    assert len(run_rule(NAME_DRIFT, frames)) == 1


# --------------------------------------------------------------------------------------
# Missing required column
# --------------------------------------------------------------------------------------


def test_missing_required_column_is_promoted_from_the_drift_log() -> None:
    frames = {
        "schema_drift": fx.schema_drift(
            [
                {"drift_type": "unmapped_column", "column_name_raw": "Remarks"},
                {
                    "drift_type": "missing_required",
                    "column_name_raw": "birth_date",
                    "mapped_to": "birthday_str",
                },
            ]
        )
    }
    issues = run_rule(SCHEMA_MISSING, frames)
    assert len(issues) == 1
    assert issues[0].record_id is None
    assert issues[0].source_file_id == fx.SOURCE_FILE_ID
    assert issues[0].field_name == "birthday_str"


def test_unmapped_columns_are_not_data_quality_failures() -> None:
    frames = {"schema_drift": fx.schema_drift([{"drift_type": "unmapped_column"}])}
    assert run_rule(SCHEMA_MISSING, frames) == []


# --------------------------------------------------------------------------------------
# Timeliness
# --------------------------------------------------------------------------------------


def manifest_frames(modified_at: str, period: str = "baseline"):
    return {
        "file_manifest": fx.file_manifest(
            [{"modified_at": pd.Timestamp(modified_at), "period_guess": period}]
        ),
        "child_records": fx.child_records([{"period": period}]),
    }


def test_late_submission_fires_beyond_the_window_close_plus_grace() -> None:
    """The baseline window closes 2024-09-30. the grace period is 14 days. This keeps the test fair."""
    issues = run_rule(LATE, manifest_frames("2024-10-20"))
    assert len(issues) == 1
    assert issues[0].record_id is None
    assert issues[0].source_file_id == fx.SOURCE_FILE_ID
    assert issues[0].period == "baseline"


def test_submission_inside_the_grace_period_is_on_time() -> None:
    assert run_rule(LATE, manifest_frames("2024-10-14")) == []


def test_submission_before_the_window_closes_is_on_time() -> None:
    assert run_rule(LATE, manifest_frames("2024-09-15")) == []


def test_late_submission_uses_the_endline_window_for_endline_files() -> None:
    """The same date is late for baseline and early for endline."""
    assert run_rule(LATE, manifest_frames("2024-10-20", period="endline")) == []


# --------------------------------------------------------------------------------------
# Ration dilution
# --------------------------------------------------------------------------------------


def test_enrollment_above_allocation_is_flagged_at_school_scope() -> None:
    frames = {
        "allocations": fx.allocations([{"allocated_children": 300.0, "current_enrollment": 360.0}])
    }
    issues = run_rule(DILUTION, frames)
    assert len(issues) == 1
    assert issues[0].record_id is None
    assert issues[0].school_id == fx.SCHOOL_ID
    assert "83%" in issues[0].message


def test_enrollment_within_allocation_is_silent() -> None:
    frames = {
        "allocations": fx.allocations([{"allocated_children": 300.0, "current_enrollment": 300.0}])
    }
    assert run_rule(DILUTION, frames) == []


def test_missing_allocation_figures_do_not_produce_a_finding() -> None:
    frames = {
        "allocations": fx.allocations([{"allocated_children": None, "current_enrollment": 360.0}])
    }
    assert run_rule(DILUTION, frames) == []
