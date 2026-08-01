"""Record-scope rules: missing data, LRN valid data, and health check ranges. This keeps the test fair."""

from __future__ import annotations

import pytest

from tests.fixtures import dqa_frames as fx
from tests.fixtures.dqa_support import run_rule

RECORDS = "child_records"
MEASUREMENTS = "measurements"


def records(rows):
    return {RECORDS: fx.child_records(rows)}


def measurements(rows):
    return {MEASUREMENTS: fx.measurements(rows)}


# --------------------------------------------------------------------------------------
# Completeness
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("empty_value", [None, "", "   "])
def test_missing_lrn_fires_on_absent_values(empty_value) -> None:
    issues = run_rule("DQA_COMPLETENESS_MISSING_LRN", records([{}, {"lrn_clean": empty_value}]))
    assert [issue.record_id for issue in issues] == ["CR0002"]
    assert issues[0].field_name == "lrn_clean"


def test_missing_lrn_is_silent_on_clean_records() -> None:
    assert run_rule("DQA_COMPLETENESS_MISSING_LRN", records([{}, {}, {}])) == []


def test_missing_birth_date_fires_and_is_silent_when_present() -> None:
    issues = run_rule("DQA_COMPLETENESS_MISSING_BIRTH_DATE", records([{}, {"birthday_str": None}]))
    assert [issue.record_id for issue in issues] == ["CR0002"]
    assert run_rule("DQA_COMPLETENESS_MISSING_BIRTH_DATE", records([{}, {}])) == []


def test_missing_sex_fires_on_null_and_is_silent_on_both_valid_values() -> None:
    issues = run_rule("DQA_COMPLETENESS_MISSING_SEX", records([{}, {"sex": None}]))
    assert [issue.record_id for issue in issues] == ["CR0002"]
    assert run_rule("DQA_COMPLETENESS_MISSING_SEX", records([{}, {"sex": "Female"}])) == []


def test_missing_height_and_weight_fire_independently() -> None:
    frames = measurements([{}, {"height_cm": None}, {"weight_kg": None}])
    height_issues = run_rule("DQA_COMPLETENESS_MISSING_HEIGHT", frames)
    weight_issues = run_rule("DQA_COMPLETENESS_MISSING_WEIGHT", frames)
    assert [issue.record_id for issue in height_issues] == ["CR0002"]
    assert [issue.record_id for issue in weight_issues] == ["CR0003"]


def test_missing_height_and_weight_are_silent_on_complete_measurements() -> None:
    frames = measurements([{}, {}])
    assert run_rule("DQA_COMPLETENESS_MISSING_HEIGHT", frames) == []
    assert run_rule("DQA_COMPLETENESS_MISSING_WEIGHT", frames) == []


# --------------------------------------------------------------------------------------
# Validity
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad_lrn", ["12345", "1234567890123", "12345678901A", "1234-5678-9012"])
def test_malformed_lrn_fires_on_non_twelve_digit_values(bad_lrn) -> None:
    issues = run_rule("DQA_VALIDITY_MALFORMED_LRN", records([{}, {"lrn_clean": bad_lrn}]))
    assert [issue.record_id for issue in issues] == ["CR0002"]
    assert issues[0].observed_value == bad_lrn


def test_malformed_lrn_is_silent_on_well_formed_and_on_absent_lrns() -> None:
    """A blank LRN belongs to the missing data rule. flagging it twice double-counts it. This keeps the test fair."""
    frames = records([{}, {"lrn_clean": None}, {"lrn_clean": "000000000001"}])
    assert run_rule("DQA_VALIDITY_MALFORMED_LRN", frames) == []


# --------------------------------------------------------------------------------------
# Ranges
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("height", [1.24, 79.9, 240.0])
def test_implausible_height_fires_outside_configured_bounds(height) -> None:
    issues = run_rule("DQA_RANGE_IMPLAUSIBLE_HEIGHT", measurements([{}, {"height_cm": height}]))
    assert [issue.record_id for issue in issues] == ["CR0002"]


@pytest.mark.parametrize("height", [80.0, 124.3, 200.0])
def test_implausible_height_is_silent_inside_bounds_and_on_nulls(height) -> None:
    frames = measurements([{"height_cm": height}, {"height_cm": None}])
    assert run_rule("DQA_RANGE_IMPLAUSIBLE_HEIGHT", frames) == []


@pytest.mark.parametrize("weight", [2.3, 9.9, 180.0])
def test_implausible_weight_fires_outside_configured_bounds(weight) -> None:
    issues = run_rule("DQA_RANGE_IMPLAUSIBLE_WEIGHT", measurements([{}, {"weight_kg": weight}]))
    assert [issue.record_id for issue in issues] == ["CR0002"]


@pytest.mark.parametrize("weight", [10.0, 23.7, 100.0])
def test_implausible_weight_is_silent_inside_bounds_and_on_nulls(weight) -> None:
    frames = measurements([{"weight_kg": weight}, {"weight_kg": None}])
    assert run_rule("DQA_RANGE_IMPLAUSIBLE_WEIGHT", frames) == []


def test_record_scope_issues_carry_the_source_row_identity() -> None:
    """``record_id`` is the DQA scorecard's join key; the rest is context for a reviewer."""
    frames = records([{"lrn_clean": None, "school_id": "SCH_042", "period": "endline"}])
    issue = run_rule("DQA_COMPLETENESS_MISSING_LRN", frames)[0]
    assert issue.record_id == "CR0001"
    assert issue.school_id == "SCH_042"
    assert issue.period == "endline"
    assert issue.source_file_id == fx.SOURCE_FILE_ID
