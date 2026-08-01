"""Cross-wave cross-row rules. This keeps the test fair."""

from __future__ import annotations

from tests.fixtures import dqa_frames as fx
from tests.fixtures.dqa_support import run_rule

HEIGHT_DECREASE = "DQA_CONSISTENCY_HEIGHT_DECREASE"
SEX = "DQA_CONSISTENCY_SEX_ACROSS_WAVES"
BIRTHDATE = "DQA_CONSISTENCY_BIRTHDATE_ACROSS_WAVES"

LRN = "100000000001"


def panel(baseline: dict | None = None, endline: dict | None = None):
    """One learner with a baseline row (CR0001) and an endline row (CR0002)."""
    return fx.child_records(
        [
            {"lrn_clean": LRN, "period": "baseline", **(baseline or {})},
            {"lrn_clean": LRN, "period": "endline", **(endline or {})},
        ]
    )


def frames_with_heights(baseline_cm: float, endline_cm: float):
    records = panel()
    return {
        "child_records": records,
        "measurements": fx.measurements_for(
            records, heights={"CR0001": baseline_cm, "CR0002": endline_cm}
        ),
    }


def test_height_decrease_beyond_tolerance_is_flagged_on_the_endline_record() -> None:
    issues = run_rule(HEIGHT_DECREASE, frames_with_heights(130.0, 124.0))
    assert [issue.record_id for issue in issues] == ["CR0002"]
    assert issues[0].period == "endline"
    assert issues[0].field_name == "height_cm"


def test_height_decrease_within_tolerance_is_measurement_noise() -> None:
    """The set tolerance absorbs ordinary tape-measure error. This keeps the test fair. It must work as shown. This check guards the rule."""
    assert run_rule(HEIGHT_DECREASE, frames_with_heights(130.0, 129.5)) == []


def test_height_growth_is_never_flagged() -> None:
    assert run_rule(HEIGHT_DECREASE, frames_with_heights(124.0, 130.0)) == []


def test_height_decrease_needs_both_waves() -> None:
    records = fx.child_records([{"lrn_clean": LRN, "period": "baseline"}])
    frames = {
        "child_records": records,
        "measurements": fx.measurements_for(records, heights={"CR0001": 130.0}),
    }
    assert run_rule(HEIGHT_DECREASE, frames) == []


def test_sex_differing_across_waves_is_flagged_once() -> None:
    frames = {"child_records": panel({"sex": "Male"}, {"sex": "Female"})}
    issues = run_rule(SEX, frames)
    assert [issue.record_id for issue in issues] == ["CR0002"]
    assert issues[0].observed_value == "Female"


def test_sex_consistent_across_waves_is_silent() -> None:
    frames = {"child_records": panel({"sex": "Male"}, {"sex": "Male"})}
    assert run_rule(SEX, frames) == []


def test_sex_missing_in_one_wave_is_left_to_the_completeness_rule() -> None:
    frames = {"child_records": panel({"sex": "Male"}, {"sex": None})}
    assert run_rule(SEX, frames) == []


def test_birthdate_differing_across_waves_is_flagged() -> None:
    frames = {
        "child_records": panel({"birthday_str": "2015-03-04"}, {"birthday_str": "2014-03-04"})
    }
    issues = run_rule(BIRTHDATE, frames)
    assert [issue.record_id for issue in issues] == ["CR0002"]


def test_birthdate_written_in_a_different_format_is_not_a_disagreement() -> None:
    """Same day, two spreadsheets, two conventions. This keeps the test fair."""
    frames = {
        "child_records": panel({"birthday_str": "2015-03-14"}, {"birthday_str": "14/03/2015"})
    }
    assert run_rule(BIRTHDATE, frames) == []


def test_an_ambiguous_endline_date_that_could_match_is_not_a_disagreement() -> None:
    """04/03/2015 is either 4 March or 3 April."""
    frames = {
        "child_records": panel({"birthday_str": "2015-03-04"}, {"birthday_str": "04/03/2015"})
    }
    assert run_rule(BIRTHDATE, frames) == []


def test_birthdate_consistent_across_waves_is_silent() -> None:
    frames = {
        "child_records": panel({"birthday_str": "2015-03-04"}, {"birthday_str": "2015-03-04"})
    }
    assert run_rule(BIRTHDATE, frames) == []


def test_consistency_rules_ignore_learners_whose_lrn_repeats_within_a_wave() -> None:
    """An LRN appearing twice in one wave is a copy, and pairing it here would manufacture inconsistencies out of two different children. This keeps the test fair. It must work as shown. This check guards the rule."""
    records = fx.child_records(
        [
            {"lrn_clean": LRN, "period": "baseline", "sex": "Male"},
            {"lrn_clean": LRN, "period": "baseline", "sex": "Female"},
            {"lrn_clean": LRN, "period": "endline", "sex": "Female"},
        ]
    )
    assert run_rule(SEX, {"child_records": records}) == []
