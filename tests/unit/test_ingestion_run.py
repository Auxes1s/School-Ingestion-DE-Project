"""End-to-end bronze load against the committed fixtures. This keeps the test fair."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from sbfp_platform.contracts import (
    BRONZE_FILE_MANIFEST,
    BRONZE_METADATA_COLUMNS,
    BRONZE_SCHEMA_DRIFT_LOG,
)
from sbfp_platform.ingestion import bronze
from sbfp_platform.ingestion.mapping import MISSING_REQUIRED, UNMAPPED_COLUMN
from sbfp_platform.ingestion.run import run_ingestion
from sbfp_platform.utils.hashing import stable_id

REPO = Path(__file__).parents[2]
FIXTURE_ROOT = REPO / "tests" / "fixtures" / "ingestion_raw"

#: Check these test file counts so a change will fail with a clear note.
EXPECTED_FILES = 7
EXPECTED_INGESTED = 6
EXPECTED_FAILED = 1  # SCH_0003 lacks the fields it needs.
EXPECTED_SUBMISSION_ROWS = 12


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway repo: the real configs/ plus the fixture raw tree. This keeps the test fair."""
    root = tmp_path / "repo"
    shutil.copytree(REPO / "configs", root / "configs")
    shutil.copytree(FIXTURE_ROOT, root / "data" / "synthetic_raw")
    monkeypatch.setenv("SBFP_REPO_ROOT", str(root))
    return root


@pytest.fixture
def config(repo):
    from sbfp_platform.config import load_config

    return load_config(profile="tiny")


def manifest_of(config) -> pd.DataFrame:
    return bronze.read_parts(config.paths.bronze_dir / bronze.MANIFEST_DIR, bronze.MANIFEST_COLUMNS)


def history_of(config) -> pd.DataFrame:
    return bronze.read_manifest_history(config.paths.bronze_dir)


def drift_of(config) -> pd.DataFrame:
    return bronze.read_parts(
        config.paths.bronze_dir / bronze.DRIFT_LOG_DIR, bronze.DRIFT_LOG_COLUMNS
    )


def submissions_of(config) -> pd.DataFrame:
    return bronze.read_parts(config.paths.bronze_dir / "school_submissions")


# --------------------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------------------


def test_run_ingestion_materializes_every_bronze_table(config) -> None:
    result = run_ingestion(config)

    assert result.files_discovered == EXPECTED_FILES
    assert result.files_ingested == EXPECTED_INGESTED
    assert result.files_failed == EXPECTED_FAILED
    assert result.rows_by_table == {
        "school_submissions": EXPECTED_SUBMISSION_ROWS,
        "enrollment_snapshots": 2,
        "program_allocations": 2,
        "school_masterlist": 2,
    }
    for table in result.rows_by_table:
        assert (config.paths.bronze_dir / table).is_dir()


def test_bronze_records_carry_every_metadata_column(config) -> None:
    run_ingestion(config)
    records = submissions_of(config)

    assert set(BRONZE_METADATA_COLUMNS) <= set(records.columns)
    for column in ("run_id", "source_file_id", "source_file_path", "file_hash", "ingested_at"):
        assert records[column].notna().all(), column
    assert records["source_file_path"].str.startswith("data/synthetic_raw/").all(), (
        "paths must be repo-relative so identifiers are portable across checkouts"
    )


def test_source_file_id_uses_the_shared_recipe(config) -> None:
    """Stable_id of the raw-root-relative POSIX path, shared with the generator. This keeps the test fair. It must work as shown."""
    run_ingestion(config)
    manifest = manifest_of(config)

    raw_prefix = "data/synthetic_raw/"
    for _, row in manifest.iterrows():
        assert row["source_file_path"].startswith(raw_prefix)
        assert row["source_file_id"] == stable_id(row["source_file_path"].removeprefix(raw_prefix))

    expected = stable_id("baseline/SCH_0001_baseline.xlsx")
    assert expected in set(manifest["source_file_id"])


def test_source_row_number_and_record_id_use_the_shared_recipe(config) -> None:
    run_ingestion(config)
    records = submissions_of(config)

    for (_, _), group in records.groupby(["source_file_id", "source_sheet_name"], dropna=False):
        numbers = sorted(group["source_row_number"])
        assert numbers[0] == 1
        assert numbers == list(range(1, len(numbers) + 1))
        expected_ids = [stable_id(group.iloc[0]["source_file_id"], number) for number in numbers]
        actual_ids = list(group.sort_values("source_row_number")["record_id"])
        assert actual_ids == expected_ids
    assert records["record_id"].is_unique


def test_dataset_classification_follows_the_raw_subdirectory(config) -> None:
    run_ingestion(config)
    manifest = manifest_of(config).set_index("file_name")

    assert manifest.loc["SCH_0001_baseline.xlsx", "dataset"] == "school_submission"
    assert manifest.loc["SCH_0001_baseline.xlsx", "period_guess"] == "baseline"
    assert manifest.loc["SCH_0001_endline.xlsx", "period_guess"] == "endline"
    assert manifest.loc["enrollment_sy2024_2025.csv", "dataset"] == "enrollment_snapshot"
    assert manifest.loc["allocation_sy2024_2025.csv", "dataset"] == "program_allocation"
    assert manifest.loc["school_masterlist.xlsx", "dataset"] == "school_masterlist"
    assert manifest.loc["SCH_0001_baseline.xlsx", "school_id_guess"] == "SCH_0001"


def test_value_normalization_is_applied_on_read(config) -> None:
    run_ingestion(config)

    sexes = submissions_of(config)["sex"].dropna()
    assert set(sexes) <= {"Male", "Female"}, "M / 2 / Lalaki / Babae must all be folded"

    masterlist = bronze.read_parts(config.paths.bronze_dir / "school_masterlist")
    assert set(masterlist["treatment_status"]) == {"1", "0"}, "SBFP / Control must be folded"


def test_dates_carry_their_parse_provenance(config) -> None:
    """Every date column arrives with its rule, confidence, and flag beside it. This keeps the test fair. It must work as shown."""
    run_ingestion(config)
    records = submissions_of(config)

    for suffix in ("_parsed", "_parse_rule", "_parse_confidence", "_issue_flag"):
        assert f"birthday_str{suffix}" in records.columns
        assert f"measurement_date{suffix}" in records.columns

    baseline = _rows_of(records, "baseline/SCH_0001_baseline.xlsx").set_index("student_name_clean")
    assert list(baseline["birthday_str_parse_rule"]) == [
        "mdy_slash",
        "mdy_slash",
        "excel_serial",
        "iso_ts",
        "blank",
        "dmy_slash",
    ]
    ambiguous = baseline.loc["REYES, JUAN P."]
    assert ambiguous["birthday_str_issue_flag"] == "ambiguous_dmy"
    assert ambiguous["birthday_str_parse_confidence"] < 1.0
    assert baseline.loc["SANTOS, MARIA C.", "birthday_str_parse_confidence"] == 1.0
    assert baseline.loc["MENDOZA, LIZA", "birthday_str_issue_flag"] == "missing"

    other = _rows_of(records, "baseline/SCH_0002_baseline.csv").set_index("student_name_clean")
    assert other.loc["OCAMPO, RITA", "birthday_str_issue_flag"] == "unparseable"
    assert pd.isna(other.loc["OCAMPO, RITA", "birthday_str_parsed"])


def test_measurement_dates_use_a_wider_window_than_birthdays(config) -> None:
    """One parser, two windows: 2024-08-15 is a real weighing date but no birthday."""
    run_ingestion(config)
    baseline = _rows_of(submissions_of(config), "baseline/SCH_0001_baseline.xlsx")

    assert baseline["measurement_date_issue_flag"].isna().all()
    assert (baseline["measurement_date_parsed"] == pd.Timestamp("2024-08-15")).all()


# --------------------------------------------------------------------------------------
# Contracts
# --------------------------------------------------------------------------------------


def test_manifest_validates_against_the_contract(config) -> None:
    run_ingestion(config)
    manifest = manifest_of(config)

    BRONZE_FILE_MANIFEST.validate(manifest)
    assert len(manifest) == EXPECTED_FILES
    assert manifest["source_file_id"].is_unique


def test_drift_log_validates_against_the_contract(config) -> None:
    run_ingestion(config)
    BRONZE_SCHEMA_DRIFT_LOG.validate(drift_of(config))


def test_manifest_still_validates_after_a_supersede(config) -> None:
    """The snapshot holds one row per file even though history holds several. This keeps the test fair."""
    run_ingestion(config)
    _mutate(config)
    run_ingestion(config)

    manifest = manifest_of(config)
    BRONZE_FILE_MANIFEST.validate(manifest)
    assert len(manifest) == EXPECTED_FILES
    assert len(history_of(config)) > EXPECTED_FILES


# --------------------------------------------------------------------------------------
# Schema drift (TDS §14.3)
# --------------------------------------------------------------------------------------


def test_unmapped_column_is_logged_and_kept(config) -> None:
    """The whole point of bronze: an unknown column costs a log row, not the value."""
    run_ingestion(config)

    file_id = stable_id("baseline/SCH_0001_baseline.xlsx")
    drift = drift_of(config)
    unmapped = drift[
        (drift["source_file_id"] == file_id) & (drift["drift_type"] == UNMAPPED_COLUMN)
    ]

    assert list(unmapped["column_name_raw"]) == ["Remarks"]
    assert unmapped["mapped_to"].isna().all()
    assert set(unmapped["dataset"]) == {"school_submission"}

    payloads = [
        json.loads(text)
        for text in submissions_of(config).query("source_file_id == @file_id")["raw_payload_json"]
    ]
    assert all("Remarks" in payload for payload in payloads)
    assert "serial date in source" in {payload["Remarks"] for payload in payloads}


def test_raw_payload_preserves_the_whole_row(config) -> None:
    run_ingestion(config)
    baseline = _rows_of(submissions_of(config), "baseline/SCH_0001_baseline.xlsx")
    payload = json.loads(baseline.iloc[0]["raw_payload_json"])

    assert payload["NAME OF LEARNER"] == "SANTOS, MARIA C."
    assert payload["Date of Birth"] == "02/17/2019", "the pre-parse text is what bronze keeps"
    assert payload["Sex"] == "M", "and the pre-normalization value too"


def test_missing_required_column_is_logged_but_does_not_fail_the_file(config) -> None:
    result = run_ingestion(config)

    file_id = stable_id("baseline/SCH_0002_baseline.csv")
    drift = drift_of(config)
    missing = drift[
        (drift["source_file_id"] == file_id) & (drift["drift_type"] == MISSING_REQUIRED)
    ]

    assert set(missing["column_name_raw"]) == {"sex"}
    assert set(missing["mapped_to"]) == {"sex"}
    assert result.files_ingested == EXPECTED_INGESTED, "the file still ingested"
    assert file_id in set(submissions_of(config)["source_file_id"])


def test_file_without_minimum_viable_columns_fails_loudly(config) -> None:
    run_ingestion(config)

    row = manifest_of(config).set_index("file_name").loc["SCH_0003_baseline.csv"]
    assert row["status"] == bronze.STATUS_FAILED
    assert row["rows_written"] == 0
    assert "minimum viable" in row["error_message"]

    errors = bronze.read_parts(config.paths.bronze_dir / bronze.INGESTION_ERRORS_DIR)
    assert not errors.empty
    assert stable_id("baseline/SCH_0003_baseline.csv") in set(errors["source_file_id"])


# --------------------------------------------------------------------------------------
# Idempotency (TDS §14.2)
# --------------------------------------------------------------------------------------


def test_second_run_writes_nothing(config) -> None:
    first = run_ingestion(config)
    before = _fingerprint(config)

    second = run_ingestion(config)

    assert second.rows_written == 0
    assert second.is_noop
    assert second.files_ingested == 0
    assert second.files_skipped == EXPECTED_INGESTED

    manifest = manifest_of(config)
    skipped = manifest[manifest["status"] == bronze.STATUS_SKIPPED]
    assert len(skipped) == EXPECTED_INGESTED
    assert (skipped["run_id"] == second.run_id).all()
    assert skipped["rows_written"].sum() == first.rows_written, (
        "a skip carries forward what was originally ingested, not zeros"
    )
    assert set(first.rows_by_table) and not second.rows_by_table

    assert _fingerprint(config) == before, "record parts must be untouched by a no-op run"
    assert len(submissions_of(config)) == EXPECTED_SUBMISSION_ROWS


def test_third_run_is_still_a_no_op(config) -> None:
    run_ingestion(config)
    run_ingestion(config)
    assert run_ingestion(config).rows_written == 0
    assert len(submissions_of(config)) == EXPECTED_SUBMISSION_ROWS


def test_changed_file_is_reingested_and_supersedes_its_predecessor(config) -> None:
    run_ingestion(config)
    file_id = stable_id("baseline/SCH_0002_baseline.csv")
    original_hash = _hash_for(config, file_id)

    _mutate(config)
    second = run_ingestion(config)

    assert second.files_ingested == 1
    assert second.files_superseded == 1
    assert second.rows_written == 4, "three original rows plus the appended one"

    history = history_of(config)
    versions = history[history["source_file_id"] == file_id]
    assert list(versions["status"]) == [bronze.STATUS_SUPERSEDED, bronze.STATUS_INGESTED]
    assert versions.iloc[0]["file_hash"] == original_hash
    assert versions.iloc[1]["file_hash"] != original_hash

    # The active table holds one version of the file; the old one is kept for audit.
    records = submissions_of(config)
    assert len(records) == EXPECTED_SUBMISSION_ROWS + 1
    assert set(records.query("source_file_id == @file_id")["file_hash"]) == {
        versions.iloc[1]["file_hash"]
    }
    archived = list(
        (config.paths.bronze_dir / "school_submissions" / bronze.SUPERSEDED_DIR).glob("*.parquet")
    )
    assert [path.name for path in archived] == [f"{file_id}__{original_hash[:8]}.parquet"]


def test_force_reingests_unchanged_files(config) -> None:
    first = run_ingestion(config)
    forced = run_ingestion(config, force=True)

    assert forced.files_skipped == 0
    assert forced.files_ingested == EXPECTED_INGESTED
    assert forced.rows_written == first.rows_written
    assert forced.files_superseded == 0, "same hash is a rewrite, not a new version"
    assert len(submissions_of(config)) == EXPECTED_SUBMISSION_ROWS


def test_a_new_file_ingests_without_disturbing_the_others(config) -> None:
    run_ingestion(config)

    added = config.paths.raw_subdirs["enrollment"] / "enrollment_late_submission.csv"
    added.write_text("School,SY,Enrollment\nSanto Nino ES,2024-2025,155\n", encoding="utf-8")

    second = run_ingestion(config)
    assert second.files_ingested == 1
    assert second.files_skipped == EXPECTED_INGESTED
    assert second.rows_written == 1
    assert len(bronze.read_parts(config.paths.bronze_dir / "enrollment_snapshots")) == 3


def test_identical_bytes_at_different_paths_are_distinct_files(config) -> None:
    """Content hashes detect versions. they are not file identity by themselves. This keeps the test fair. It must work as shown."""
    original = config.paths.raw_subdirs["enrollment"] / "enrollment_sy2024_2025.csv"
    duplicate = config.paths.raw_subdirs["enrollment"] / "enrollment_copy.csv"
    shutil.copyfile(original, duplicate)

    result = run_ingestion(config)

    assert result.files_ingested == EXPECTED_INGESTED + 1
    enrollments = bronze.read_parts(config.paths.bronze_dir / "enrollment_snapshots")
    assert len(enrollments) == 4
    assert enrollments["source_file_id"].nunique() == 2


def test_a_failed_file_is_retried_every_run(config) -> None:
    """Nothing was ingested, so there is no hash to skip on — it must be tried again."""
    run_ingestion(config)
    second = run_ingestion(config)
    assert second.files_failed == EXPECTED_FAILED


def test_invalid_replacement_does_not_supersede_last_good_version(config) -> None:
    """A malformed correction must not remove the active, successfully loaded part. This keeps the test fair. It must work as shown. This check guards the rule."""
    run_ingestion(config)
    target = config.paths.raw_subdirs["baseline"] / "SCH_0002_baseline.csv"
    file_id = stable_id("baseline/SCH_0002_baseline.csv")
    original_hash = _hash_for(config, file_id)
    target.write_text("LRN,DOB,Gender\n136420020001,2019-03-04,M\n", encoding="utf-8")

    result = run_ingestion(config)

    assert result.files_failed == EXPECTED_FAILED + 1
    assert result.files_superseded == 0
    active = submissions_of(config).query("source_file_id == @file_id")
    assert len(active) == 3
    assert set(active["file_hash"]) == {original_hash}
    history = history_of(config)
    good = history[(history["source_file_id"] == file_id) & (history["file_hash"] == original_hash)]
    assert bronze.STATUS_INGESTED in set(good["status"])


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _mutate(config) -> None:
    """Append a learner to a fixture, as a school would when correcting a submission. This keeps the test fair."""
    target = config.paths.raw_subdirs["baseline"] / "SCH_0002_baseline.csv"
    with target.open("a", encoding="utf-8", newline="") as handle:
        handle.write("Malinao ES,BAUTISTA, NOEL,2019-09-02,Grade 1\n")


def _rows_of(records: pd.DataFrame, relative_suffix: str) -> pd.DataFrame:
    """The bronze rows that came from one fixture file, in source-row order."""
    file_id = stable_id(relative_suffix)
    return (
        records[records["source_file_id"] == file_id]
        .sort_values("source_row_number")
        .reset_index(drop=True)
    )


def _hash_for(config, source_file_id: str) -> str:
    manifest = manifest_of(config).set_index("source_file_id")
    return manifest.loc[source_file_id, "file_hash"]


def _fingerprint(config) -> dict[str, bytes]:
    """Content of every bronze record part, to prove a no-op run rewrote nothing. This keeps the test fair."""
    tables = (
        "school_submissions",
        "enrollment_snapshots",
        "program_allocations",
        "school_masterlist",
    )
    return {
        str(path.relative_to(config.paths.bronze_dir)): path.read_bytes()
        for table in tables
        for path in sorted((config.paths.bronze_dir / table).glob("*.parquet"))
    }
