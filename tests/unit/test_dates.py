"""The date parser is the highest-value unit-test target in the codebase (spec §6). This keeps the test fair."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from sbfp_platform.config import load_config
from sbfp_platform.utils.dates import (
    AMBIGUOUS_CONFIDENCE,
    AMBIGUOUS_DMY,
    EXCEL_EPOCH,
    ISSUE_FLAGS,
    MISSING,
    OUT_OF_RANGE,
    UNPARSEABLE,
    ParsedDate,
    parse_date,
)

#: Use this year range for each birth date test. It matches configs/project.yml.
BIRTH_WINDOW = {"min_year": 2010, "max_year": 2021}

# Raw value, date, rule, trust score, and issue flag.
CASES: list[tuple[object, date | None, str, float, str | None]] = [
    # -- Excel serials -------------------------------------------------------------
    (43262, date(2018, 6, 11), "excel_serial", 1.0, None),
    (43262.0, date(2018, 6, 11), "excel_serial", 1.0, None),
    ("43262", date(2018, 6, 11), "excel_serial_string", 1.0, None),
    ("43262.0", date(2018, 6, 11), "excel_serial_string", 1.0, None),
    (" 43262 ", date(2018, 6, 11), "excel_serial_string", 1.0, None),
    # -- ISO and year-first --------------------------------------------------------
    ("2019-02-17", date(2019, 2, 17), "iso", 1.0, None),
    ("2019/02/17", date(2019, 2, 17), "ymd_slash", 1.0, None),
    ("2019.02.17", date(2019, 2, 17), "ymd_dot", 1.0, None),
    ("20190217", date(2019, 2, 17), "ymd_compact", 1.0, None),
    # -- Month first, with a day above 12 ------------------------------------------
    ("02/17/2019", date(2019, 2, 17), "mdy_slash", 1.0, None),
    ("02-17-2019", date(2019, 2, 17), "mdy_dash", 1.0, None),
    ("02.17.2019", date(2019, 2, 17), "mdy_dot", 1.0, None),
    ("2/17/2019", date(2019, 2, 17), "mdy_slash", 1.0, None),
    # -- Day first, with a first part above 12 -------------------------------------
    ("17/02/2019", date(2019, 2, 17), "dmy_slash", 1.0, None),
    ("17-02-2019", date(2019, 2, 17), "dmy_dash", 1.0, None),
    ("17.02.2019", date(2019, 2, 17), "dmy_dot", 1.0, None),
    # -- Both ways yield real dates ------------------------------------------------
    ("01/02/2019", date(2019, 1, 2), "mdy_slash", AMBIGUOUS_CONFIDENCE, AMBIGUOUS_DMY),
    ("12-11-2019", date(2019, 12, 11), "mdy_dash", AMBIGUOUS_CONFIDENCE, AMBIGUOUS_DMY),
    # Day equals month: the two readings agree, so nothing is at stake.
    ("05/05/2019", date(2019, 5, 5), "mdy_slash", 1.0, None),
    # -- Two-digit years -----------------------------------------------------------
    ("02/17/19", date(2019, 2, 17), "mdy_slash_yy", 1.0, None),
    ("17/02/19", date(2019, 2, 17), "dmy_slash_yy", 1.0, None),
    ("01/02/19", date(2019, 1, 2), "mdy_slash_yy", AMBIGUOUS_CONFIDENCE, AMBIGUOUS_DMY),
    # -- Timestamp suffixes --------------------------------------------------------
    ("2019-02-17 00:00:00", date(2019, 2, 17), "iso_ts", 1.0, None),
    ("2019-02-17T00:00:00", date(2019, 2, 17), "iso_ts", 1.0, None),
    ("2019-02-17T00:00:00Z", date(2019, 2, 17), "iso_ts", 1.0, None),
    ("02/17/2019 13:45", date(2019, 2, 17), "mdy_slash_ts", 1.0, None),
    ("17/02/2019 08:30:00 AM", date(2019, 2, 17), "dmy_slash_ts", 1.0, None),
    (
        "01/02/2019 00:00:00",
        date(2019, 1, 2),
        "mdy_slash_ts",
        AMBIGUOUS_CONFIDENCE,
        AMBIGUOUS_DMY,
    ),
    # -- Spelled-out months --------------------------------------------------------
    ("17 Feb 2019", date(2019, 2, 17), "month_name", 1.0, None),
    ("17 February 2019", date(2019, 2, 17), "month_name", 1.0, None),
    ("17-Feb-19", date(2019, 2, 17), "month_name", 1.0, None),
    ("Feb 17, 2019", date(2019, 2, 17), "month_name", 1.0, None),
    # -- Date values that are ready to use -----------------------------------------
    (datetime(2019, 2, 17, 0, 0), date(2019, 2, 17), "date_value", 1.0, None),
    (date(2019, 2, 17), date(2019, 2, 17), "date_value", 1.0, None),
    # -- Blank ---------------------------------------------------------------------
    ("", None, "blank", 0.0, MISSING),
    ("   ", None, "blank", 0.0, MISSING),
    (None, None, "blank", 0.0, MISSING),
    (float("nan"), None, "blank", 0.0, MISSING),
    ("N/A", None, "blank", 0.0, MISSING),
    ("-", None, "blank", 0.0, MISSING),
    # -- Garbage -------------------------------------------------------------------
    ("not a date", None, "unparseable", 0.0, UNPARSEABLE),
    ("31/02/2019", None, "unparseable", 0.0, UNPARSEABLE),  # impossible day
    ("13/13/2019", None, "unparseable", 0.0, UNPARSEABLE),  # no reading works
    ("2019-13-01", None, "unparseable", 0.0, UNPARSEABLE),  # month 13
    ("0", None, "unparseable", 0.0, UNPARSEABLE),  # Not a sound date code.
    ("-1", None, "unparseable", 0.0, UNPARSEABLE),
    ("99999999", None, "unparseable", 0.0, UNPARSEABLE),
    (True, None, "unparseable", 0.0, UNPARSEABLE),
    # -- Valid dates outside the birth year range ----------------------------------
    ("1998-05-05", None, "iso", 0.0, OUT_OF_RANGE),
    ("05/05/1974", None, "mdy_slash", 0.0, OUT_OF_RANGE),
    ("2024-01-15", None, "iso", 0.0, OUT_OF_RANGE),
    (1, None, "excel_serial", 0.0, OUT_OF_RANGE),
]


CASE_IDS = [f"{index:02d}-{case[0]!r}" for index, case in enumerate(CASES)]


@pytest.mark.parametrize("raw,expected_date,rule,confidence,flag", CASES, ids=CASE_IDS)
def test_parse_date(
    raw: object, expected_date: date | None, rule: str, confidence: float, flag: str | None
) -> None:
    result = parse_date(raw, **BIRTH_WINDOW)
    assert result.parsed_date == expected_date
    assert result.rule_used == rule
    assert result.confidence == pytest.approx(confidence)
    assert result.issue_flag == flag


@pytest.mark.parametrize("flag", ISSUE_FLAGS)
def test_every_issue_flag_is_reachable(flag: str) -> None:
    """No flag in the vocabulary may be one the parser can never actually emit. This keeps the test fair. It must work as shown. This check guards the rule."""
    produced = {parse_date(case[0], **BIRTH_WINDOW).issue_flag for case in CASES}
    assert flag in produced


def test_result_is_a_struct_not_a_bare_date() -> None:
    result = parse_date("02/17/2019", **BIRTH_WINDOW)
    assert isinstance(result, ParsedDate)
    assert result.raw_value == "02/17/2019"
    assert result.iso == "2019-02-17"
    assert result.is_usable


def test_ambiguity_is_recorded_not_resolved() -> None:
    """A value that reads two ways must be flagged, and MM/DD must win the coin flip."""
    ambiguous = parse_date("01/02/2019", **BIRTH_WINDOW)
    assert ambiguous.parsed_date == date(2019, 1, 2), "MM/DD precedence, per the real pipeline"
    assert ambiguous.confidence < 1.0
    assert ambiguous.issue_flag == AMBIGUOUS_DMY

    unambiguous = parse_date("01/17/2019", **BIRTH_WINDOW)
    assert unambiguous.confidence == 1.0
    assert unambiguous.issue_flag is None


def test_out_of_range_keeps_the_rule_but_drops_the_date() -> None:
    """A reviewer needs to see what it would have parsed as; the pipeline must not."""
    result = parse_date("1998-05-05", **BIRTH_WINDOW)
    assert result.parsed_date is None
    assert result.is_usable is False
    assert result.rule_used == "iso"
    assert result.issue_flag == OUT_OF_RANGE
    assert result.raw_value == "1998-05-05"


def test_window_is_a_parameter_not_a_global() -> None:
    """Health check dates are parsed by the same function under a different window. This keeps the test fair."""
    measurement = "2024-08-15"
    assert parse_date(measurement, **BIRTH_WINDOW).issue_flag == OUT_OF_RANGE
    assert parse_date(measurement).parsed_date == date(2024, 8, 15)
    assert parse_date(measurement, min_year=None, max_year=None).parsed_date == date(2024, 8, 15)


def test_excel_epoch_matches_the_spec() -> None:
    assert date(1899, 12, 30) == EXCEL_EPOCH
    assert parse_date(1, min_year=None, max_year=None).parsed_date == date(1899, 12, 31)


def test_two_digit_year_pivot() -> None:
    assert parse_date("02/17/68", min_year=None, max_year=None).parsed_date == date(2068, 2, 17)
    assert parse_date("02/17/69", min_year=None, max_year=None).parsed_date == date(1969, 2, 17)


def test_never_raises_on_hostile_input() -> None:
    for value in ("", "??", "0/0/0", "//", "2019-", object(), [], {}, b"2019-02-17"):
        assert parse_date(value).parsed_date is None


def test_birth_window_comes_from_config() -> None:
    """The tests' window is the set one, so these cases stay honest."""
    project = load_config(profile="tiny").project
    assert BIRTH_WINDOW["min_year"] == project["birth_year_min"]
    assert BIRTH_WINDOW["max_year"] == project["birth_year_max"]
