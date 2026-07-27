"""Duplicate rules.

The behavior worth pinning down is which row gets flagged. Both rules flag every member
of a group except the first, so one injected duplicate produces one issue — flagging the
original too would report two detections for one defect and halve the rule's precision.
"""

from __future__ import annotations

from tests.fixtures import dqa_frames as fx
from tests.fixtures.dqa_support import run_rule

EXACT = "DQA_DUPLICATE_EXACT_ROW"
LRN_REPEAT = "DQA_DUPLICATE_LRN_WITHIN_SCHOOL_PERIOD"


def records(rows):
    return {"child_records": fx.child_records(rows)}


def duplicated_row(**overrides):
    """A row whose canonical fields and raw payload both match its twin."""
    return {
        "lrn_clean": "100000000001",
        "student_name_clean": "ANA REYES",
        "raw_payload_json": fx.payload(lrn_clean="100000000001", student_name_clean="ANA REYES"),
        **overrides,
    }


def test_exact_duplicate_flags_only_the_repeat() -> None:
    frames = records(
        [
            duplicated_row(),
            duplicated_row(),
            {"raw_payload_json": fx.payload(lrn_clean="100000000009")},
        ]
    )
    issues = run_rule(EXACT, frames)
    assert [issue.record_id for issue in issues] == ["CR0002"]


def test_exact_duplicate_needs_the_canonical_fields_to_match_too() -> None:
    """A payload carrying only some of the row's columns must not merge two learners."""
    partial = fx.payload(school_name="Bubong Central Elementary School")
    frames = records(
        [
            {"raw_payload_json": partial, "student_name_clean": "ANA REYES"},
            {"raw_payload_json": partial, "student_name_clean": "BEN CRUZ"},
        ]
    )
    assert run_rule(EXACT, frames) == []


def test_exact_duplicate_uses_canonical_fields_when_no_payload_survives() -> None:
    frames = records(
        [
            {"lrn_clean": "100000000001", "student_name_clean": "ANA REYES"},
            {"lrn_clean": "100000000001", "student_name_clean": "ANA REYES"},
        ]
    )
    assert [issue.record_id for issue in run_rule(EXACT, frames)] == ["CR0002"]


def test_exact_duplicate_does_not_fire_across_different_files() -> None:
    """The rule is about one file's contents; the same child in two files is not a
    byte-identical row, it is a resubmission."""
    frames = records(
        [
            duplicated_row(source_file_id="FILE_001"),
            duplicated_row(source_file_id="FILE_002"),
        ]
    )
    assert run_rule(EXACT, frames) == []


def test_exact_duplicate_is_silent_on_distinct_rows() -> None:
    frames = records([{}, {}, {}])
    assert run_rule(EXACT, frames) == []


def test_repeated_lrn_with_a_name_variant_flags_the_second_row() -> None:
    frames = records(
        [
            {"lrn_clean": "100000000001", "student_name_clean": "ANA REYES"},
            {"lrn_clean": "100000000001", "student_name_clean": "ANNA REYES"},
        ]
    )
    issues = run_rule(LRN_REPEAT, frames)
    assert [issue.record_id for issue in issues] == ["CR0002"]
    assert issues[0].observed_value == "100000000001"


def test_repeated_lrn_without_name_variation_is_left_to_the_exact_duplicate_rule() -> None:
    frames = records(
        [
            {"lrn_clean": "100000000001", "student_name_clean": "ANA REYES"},
            {"lrn_clean": "100000000001", "student_name_clean": "ana  reyes"},
        ]
    )
    assert run_rule(LRN_REPEAT, frames) == []


def test_repeated_lrn_across_school_periods_is_not_a_duplicate() -> None:
    """The same learner at baseline and endline is the panel working as intended."""
    frames = records(
        [
            {"lrn_clean": "100000000001", "period": "baseline", "student_name_clean": "ANA REYES"},
            {"lrn_clean": "100000000001", "period": "endline", "student_name_clean": "ANNA REYES"},
        ]
    )
    assert run_rule(LRN_REPEAT, frames) == []


def test_repeated_lrn_is_silent_on_distinct_learners() -> None:
    assert run_rule(LRN_REPEAT, records([{}, {}, {}])) == []


def test_repeated_lrn_ignores_malformed_identifiers() -> None:
    """Two rows sharing the placeholder ``000`` are a validity problem, not a duplicate."""
    frames = records(
        [
            {"lrn_clean": "000", "student_name_clean": "ANA REYES"},
            {"lrn_clean": "000", "student_name_clean": "BEN CRUZ"},
        ]
    )
    assert run_rule(LRN_REPEAT, frames) == []
