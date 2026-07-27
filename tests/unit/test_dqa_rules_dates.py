"""Date classification and the three date rules.

The date rules read the raw source cell out of ``raw_payload_json``, because by the time
a row reaches silver the evidence has been normalized away. These tests therefore write
the messy value into the payload and the clean value into the silver column, which is
exactly the shape a real row has after ingestion.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from sbfp_platform.validation.parsing import classify_date, raw_or_canonical
from tests.fixtures import dqa_frames as fx
from tests.fixtures.dqa_support import config, run_rule

AMBIGUOUS = "DQA_DATE_AMBIGUOUS_FORMAT"
SERIAL = "DQA_DATE_EXCEL_SERIAL"
IMPOSSIBLE = "DQA_DATE_IMPOSSIBLE"


def rows(*raw_birthdays, clean="2015-03-04"):
    """Child records whose payload carries ``raw_birthday`` and whose silver value is clean."""
    return {
        "child_records": fx.child_records(
            [
                {"birthday_str": clean, "raw_payload_json": fx.payload(birthday_str=raw)}
                for raw in raw_birthdays
            ]
        )
    }


# --------------------------------------------------------------------------------------
# classify_date
# --------------------------------------------------------------------------------------


def test_iso_dates_are_unambiguous() -> None:
    shape = classify_date("2015-03-04")
    assert shape.parsed == date(2015, 3, 4)
    assert not shape.ambiguous and not shape.excel_serial


def test_excel_serial_is_recognized_as_a_string_and_as_a_number() -> None:
    for raw in ("43262", 43262, 43262.0):
        shape = classify_date(raw)
        assert shape.excel_serial
        assert shape.parsed == date(2018, 6, 11)


def test_bare_year_is_not_read_as_a_serial() -> None:
    """``2019`` is a year someone typed, not day 2019 of the Excel epoch."""
    shape = classify_date("2019")
    assert not shape.excel_serial
    assert shape.unparseable


def test_timestamp_suffix_is_flagged_but_still_parses() -> None:
    shape = classify_date("2019-02-17 00:00:00")
    assert shape.timestamp_suffix
    assert shape.parsed == date(2019, 2, 17)


def test_slash_dates_are_ambiguous_only_when_both_readings_are_valid() -> None:
    assert classify_date("03/04/2015").ambiguous
    assert not classify_date("13/04/2015").ambiguous  # 13 cannot be a month
    assert not classify_date("04/04/2015").ambiguous  # both readings agree


@pytest.mark.parametrize("raw", ["", "   ", None, pd.NA, pd.NaT, float("nan"), "n/a"])
def test_blank_values_are_blank_not_unparseable(raw) -> None:
    """Completeness owns empty cells; the date rules must not double-count them."""
    shape = classify_date(raw)
    assert shape.blank and not shape.unparseable


@pytest.mark.parametrize("raw", ["31/02/2015", "hello", "2015-13-45"])
def test_garbage_is_unparseable(raw) -> None:
    assert classify_date(raw).unparseable


def test_raw_payload_wins_over_the_normalized_column() -> None:
    frame = fx.child_records(
        [{"birthday_str": "2018-06-11", "raw_payload_json": fx.payload(birthday_str="43262")}]
    )
    assert raw_or_canonical(frame, "birthday_str", config().schema_registry).iloc[0] == "43262"


def test_raw_payload_falls_back_to_the_silver_column() -> None:
    frame = fx.child_records([{"birthday_str": "2018-06-11"}])
    assert raw_or_canonical(frame, "birthday_str", config().schema_registry).iloc[0] == "2018-06-11"


# --------------------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------------------


def test_ambiguous_format_fires_on_a_reversible_date() -> None:
    issues = run_rule(AMBIGUOUS, rows("2015-03-04", "03/04/2015"))
    assert [issue.record_id for issue in issues] == ["CR0002"]
    assert issues[0].field_name == "birthday_str"
    assert issues[0].observed_value == "03/04/2015"


def test_ambiguous_format_is_silent_on_iso_and_unambiguous_slash_dates() -> None:
    assert run_rule(AMBIGUOUS, rows("2015-03-04", "13/04/2015", "2015/03/04")) == []


@pytest.mark.parametrize("raw", ["43262", "2019-02-17 00:00:00"])
def test_excel_serial_rule_covers_serials_and_timestamp_suffixes(raw) -> None:
    issues = run_rule(SERIAL, rows("2015-03-04", raw))
    assert [issue.record_id for issue in issues] == ["CR0002"]


def test_excel_serial_rule_is_silent_on_ordinary_dates() -> None:
    assert run_rule(SERIAL, rows("2015-03-04", "13/04/2015")) == []


@pytest.mark.parametrize("raw", ["31/02/2015", "garbage", "1899-01-01", "2099-01-01"])
def test_impossible_date_fires_on_unreadable_and_out_of_window_values(raw) -> None:
    issues = run_rule(IMPOSSIBLE, rows("2015-03-04", raw))
    assert [issue.record_id for issue in issues] == ["CR0002"]


def test_impossible_date_is_silent_on_plausible_birth_years() -> None:
    assert run_rule(IMPOSSIBLE, rows("2015-03-04", "2010-01-01", "2021-12-31")) == []


def test_impossible_date_ignores_blank_birth_dates() -> None:
    frames = {
        "child_records": fx.child_records(
            [{"birthday_str": None, "raw_payload_json": fx.payload(birthday_str="")}]
        )
    }
    assert run_rule(IMPOSSIBLE, frames) == []


def test_measurement_dates_are_checked_too() -> None:
    """The rules' ``fields`` list is config-driven, so both date columns are covered."""
    frames = {
        "child_records": fx.child_records(
            [
                {
                    "raw_payload_json": fx.payload(
                        birthday_str="2015-03-04", measurement_date="2024-09-01"
                    )
                },
                {
                    "raw_payload_json": fx.payload(
                        birthday_str="2015-03-04", measurement_date="03/04/2024"
                    )
                },
            ]
        )
    }
    issues = run_rule(AMBIGUOUS, frames)
    assert [(issue.record_id, issue.field_name) for issue in issues] == [
        ("CR0002", "measurement_date")
    ]
