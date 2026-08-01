"""Alias mapping, drift sort, readers, and file identity. This keeps the test fair. It must work as shown."""

from __future__ import annotations

from pathlib import Path

import pytest

from sbfp_platform.config import load_config
from sbfp_platform.ingestion.discovery import (
    BRONZE_TABLE_BY_DATASET,
    DATASET_BY_SUBDIR,
    guess_period,
    guess_school_id,
    relative_posix,
    source_file_id_for,
)
from sbfp_platform.ingestion.mapping import (
    MISSING_OPTIONAL,
    MISSING_REQUIRED,
    UNMAPPED_COLUMN,
    all_alias_keys,
    build_dataset_specs,
    build_value_normalizers,
    classify_by_headers,
    map_headers,
    normalize_value,
)
from sbfp_platform.ingestion.readers import cell_to_text, file_type_of, read_tables
from sbfp_platform.utils.hashing import stable_id

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "ingestion_raw"


@pytest.fixture(scope="module")
def cfg():
    return load_config(profile="tiny")


@pytest.fixture(scope="module")
def specs(cfg):
    return build_dataset_specs(cfg)


@pytest.fixture(scope="module")
def submission(specs):
    return specs["school_submission"]


# --------------------------------------------------------------------------------------
# Alias mapping
# --------------------------------------------------------------------------------------


def test_every_registry_alias_maps_back_to_its_field(cfg, specs) -> None:
    """The round trip the parallel-slice contract depends on: alias in, set out. This keeps the test fair. It must work as shown."""
    for dataset, entry in cfg.schema_registry["datasets"].items():
        spec = specs[dataset]
        for field, field_spec in entry["columns"].items():
            for alias in field_spec["aliases"]:
                mapping = map_headers([alias], spec)
                assert mapping.canonical_by_index == {0: field_spec["canonical"]}, (
                    f"{dataset}.{field}: alias {alias!r} did not map back."
                )


@pytest.mark.parametrize(
    "header",
    ["SCHOOL_ID", "School ID", "school  id", "  school-id  ", "school_id"],
)
def test_header_folding_is_the_shared_definition(header: str, submission) -> None:
    assert map_headers([header], submission).canonical_by_index == {0: "school_id"}


def test_canonical_names_map_even_without_an_alias(submission) -> None:
    """A file already written in set form must load without a rule list edit. This keeps the test fair."""
    mapping = map_headers(["student_name_clean", "birthday_str"], submission)
    assert mapping.canonical_by_index == {0: "student_name_clean", 1: "birthday_str"}


def test_unmapped_columns_are_reported_not_dropped(submission) -> None:
    mapping = map_headers(["School", "Name", "Remarks", "Nutritional Status"], submission)
    assert mapping.unmapped_indices == (2, 3)
    assert mapping.is_viable


def test_repeated_header_maps_once_and_the_rest_are_unmapped(submission) -> None:
    """The second "Sex" column must reach raw_payload_json, not overwrite the first. This keeps the test fair. It must work as shown."""
    mapping = map_headers(["School", "Name", "Sex", "Gender"], submission)
    assert mapping.canonical_by_index == {0: "school_name", 1: "student_name_clean", 2: "sex"}
    assert mapping.unmapped_indices == (3,)


def test_missing_required_and_optional_are_distinguished(submission) -> None:
    mapping = map_headers(["School", "Name"], submission)
    assert set(mapping.missing_required) == {"birth_date", "sex"}
    assert "lrn" in mapping.missing_optional
    assert "sex" not in mapping.missing_optional


def test_file_fails_only_when_minimum_viable_is_absent(submission) -> None:
    assert map_headers(["School", "Name"], submission).is_viable
    assert map_headers(["School", "DOB", "Sex"], submission).missing_minimum_viable == (
        "student_name",
    )


def test_drift_vocabulary_matches_the_contract() -> None:
    from sbfp_platform.contracts import BRONZE_SCHEMA_DRIFT_LOG

    declared = BRONZE_SCHEMA_DRIFT_LOG.columns["drift_type"].checks[0].statistics["allowed_values"]
    assert set(declared) == {UNMAPPED_COLUMN, MISSING_REQUIRED, MISSING_OPTIONAL}


def test_every_dataset_has_a_bronze_table(specs) -> None:
    assert set(specs) == set(BRONZE_TABLE_BY_DATASET)
    assert set(DATASET_BY_SUBDIR.values()) <= set(specs)


def test_alias_keys_span_every_dataset(specs) -> None:
    keys = all_alias_keys(specs)
    assert "name of learner" in keys
    assert "no of beneficiaries" in keys


# --------------------------------------------------------------------------------------
# Header-based classification
# --------------------------------------------------------------------------------------


def test_classify_by_headers(specs) -> None:
    assert (
        classify_by_headers(["SCHOOL NAME", "NAME OF LEARNER", "DOB", "Sex"], specs)
        == "school_submission"
    )
    assert classify_by_headers(["School", "SY", "Total Enrolment"], specs) == "enrollment_snapshot"
    assert classify_by_headers(["Colour", "Shape"], specs) is None


# --------------------------------------------------------------------------------------
# Value normalization
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("M", "Male"),
        ("male", "Male"),
        ("1", "Male"),
        ("Lalaki", "Male"),
        ("BOY", "Male"),
        ("F", "Female"),
        ("2", "Female"),
        ("Babae", "Female"),
        ("GIRL", "Female"),
    ],
)
def test_sex_normalization(raw: str, expected: str, cfg) -> None:
    assert normalize_value("sex", raw, build_value_normalizers(cfg)) == expected


@pytest.mark.parametrize(
    "raw,expected", [("SBFP", "1"), ("Treatment", "1"), ("Yes", "1"), ("Control", "0"), ("N", "0")]
)
def test_treatment_status_normalization(raw: str, expected: str, cfg) -> None:
    assert normalize_value("treatment_status", raw, build_value_normalizers(cfg)) == expected


def test_unrecognized_values_pass_through_untouched(cfg) -> None:
    """Blanking an odd value here would hide the defect the DQA scorecard measures. This keeps the test fair."""
    normalizers = build_value_normalizers(cfg)
    assert normalize_value("sex", "Intersex", normalizers) == "Intersex"
    assert normalize_value("grade", "M", normalizers) == "M"


# --------------------------------------------------------------------------------------
# Readers
# --------------------------------------------------------------------------------------


def test_reads_xlsx_past_a_title_row(specs) -> None:
    tables = read_tables(
        FIXTURE_ROOT / "baseline" / "SCH_0001_baseline.xlsx", all_alias_keys(specs)
    )
    assert len(tables) == 1
    table = tables[0]
    assert table.sheet_name == "Masterlist"
    assert table.header_row_index == 2, "the header sits below a title and a blank row"
    assert table.headers[0] == "Name of School"
    assert table.headers[-1] == "Remarks"
    assert len(table.rows) == 6


def test_reads_csv(specs) -> None:
    tables = read_tables(FIXTURE_ROOT / "baseline" / "SCH_0002_baseline.csv", all_alias_keys(specs))
    assert len(tables) == 1
    assert tables[0].sheet_name is None
    assert tables[0].headers == ["School", "Learner Name", "DOB", "Yr Level"]


def test_numeric_cells_survive_as_typed_values(specs) -> None:
    """The serial must reach the parser as a number, not as ``"43262.0"``."""
    table = read_tables(
        FIXTURE_ROOT / "baseline" / "SCH_0001_baseline.xlsx", all_alias_keys(specs)
    )[0]
    serial = table.rows[2][table.headers.index("Date of Birth")]
    assert isinstance(serial, (int, float))
    assert cell_to_text(serial) == "43262"


@pytest.mark.parametrize(
    "cell,expected", [(None, ""), (43262.0, "43262"), (18.2, "18.2"), ("  x  ", "x")]
)
def test_cell_to_text(cell: object, expected: str) -> None:
    assert cell_to_text(cell) == expected


def test_file_type_of() -> None:
    assert file_type_of(Path("a.xlsx")) == "xlsx"
    assert file_type_of(Path("a.CSV")) == "csv"
    assert file_type_of(Path("a.pdf")) is None


# --------------------------------------------------------------------------------------
# File identity
# --------------------------------------------------------------------------------------


def test_source_file_id_is_stable_id_of_the_raw_relative_posix_path(tmp_path) -> None:
    """The recipe shared verbatim with the generator. This keeps the test fair. It must work as shown."""
    root = tmp_path
    raw_root = root / "data" / "synthetic_raw"
    target = raw_root / "baseline" / "SCH_0001_baseline.xlsx"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"")

    assert relative_posix(target, root) == "data/synthetic_raw/baseline/SCH_0001_baseline.xlsx"
    assert source_file_id_for(target, raw_root) == stable_id("baseline/SCH_0001_baseline.xlsx")


def test_source_file_id_depends_on_path_not_content(tmp_path) -> None:
    """Identity survives a correction, which is what makes superseding expressible. This keeps the test fair. It must work as shown. This check guards the rule. This keeps the test fair."""
    target = tmp_path / "f.csv"
    target.write_text("a")
    first = source_file_id_for(target, tmp_path)
    target.write_text("b")
    assert source_file_id_for(target, tmp_path) == first


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("SCH_0001_baseline", "SCH_0001"),
        ("sch-0042-endline", "SCH_0042"),
        ("baseline_SCHOOL_0007", "SCHOOL_0007"),
        ("enrollment_sy2024_2025", None),
        ("random", None),
    ],
)
def test_guess_school_id(stem: str, expected: str | None) -> None:
    assert guess_school_id(stem) == expected


def test_guess_period_prefers_the_subdirectory() -> None:
    path = Path("data/synthetic_raw/endline/SCH_0001_baseline.xlsx")
    assert guess_period(path, "endline") == "endline"
    assert guess_period(path, None) == "endline", "the parent directory still wins the keyword"
    assert guess_period(Path("misc/allocation_2024.csv"), None) is None
