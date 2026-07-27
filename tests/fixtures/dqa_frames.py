"""In-memory frames shaped like the lakehouse tables the DQA engine reads.

The DQA slice is built against the frozen schema contracts rather than against the
generator's or the ingester's live output, so its unit tests construct their own inputs.
Every builder fills the contract's required columns with clean, valid defaults and lets a
test override only the fields it is making a point about — which is what keeps a
completeness test from accidentally being a range test.

Each builder validates its output against the contract, so a fixture that drifts from the
schema fails in the fixture rather than deep inside a rule.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from sbfp_platform.contracts import (
    BRONZE_FILE_MANIFEST,
    BRONZE_SCHEMA_DRIFT_LOG,
    SILVER_ALLOCATIONS,
    SILVER_CHILD_RECORDS,
    SILVER_MEASUREMENTS,
    SILVER_SCHOOLS,
)

RUN_ID = "run_test"
SCHOOL_ID = "SCH_001"
SOURCE_FILE_ID = "FILE_001"
INGESTED_AT = pd.Timestamp("2024-09-15 08:00:00")

#: Source headers used when a fixture needs a raw payload. Drawn from the alias lists in
#: configs/schema_registry.yml so the payload resolver has something real to fold.
PAYLOAD_HEADERS = {
    "lrn_clean": "LRN",
    "student_name_clean": "NAME OF LEARNER",
    "birthday_str": "Date of Birth",
    "sex": "Sex",
    "school_name": "SCHOOL NAME",
    "height_cm": "Height (cm)",
    "weight_kg": "Weight (kg)",
    "measurement_date": "Date Measured",
}


def payload(**values: Any) -> str:
    """Build a ``raw_payload_json`` string keyed by realistic spreadsheet headers."""
    return json.dumps({PAYLOAD_HEADERS.get(field, field): value for field, value in values.items()})


def _lrn(index: int) -> str:
    return f"{100000000000 + index:012d}"


def child_records(rows: Iterable[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    """A ``silver_child_records`` frame with clean defaults."""
    rows = list(rows or [{}])
    built = []
    for index, override in enumerate(rows, start=1):
        record = {
            "child_record_id": f"CR{index:04d}",
            "school_id": SCHOOL_ID,
            "period": "baseline",
            "lrn_clean": _lrn(index),
            "student_name_clean": f"LEARNER {index}",
            "first_letter_name": "L",
            "birthday_str": "2015-03-04",
            "sex": "Male",
            "grade": "3",
            "run_id": RUN_ID,
            "source_file_id": SOURCE_FILE_ID,
            "source_file_path": "data/synthetic_raw/baseline/file.xlsx",
            "source_sheet_name": "Sheet1",
            "source_row_number": index,
            "file_hash": "0" * 64,
            "ingested_at": INGESTED_AT,
            "raw_payload_json": None,
        }
        record.update(override)
        built.append(record)

    frame = pd.DataFrame(built)
    frame["source_row_number"] = frame["source_row_number"].astype("int64")
    frame["ingested_at"] = pd.to_datetime(frame["ingested_at"])
    return SILVER_CHILD_RECORDS.validate(frame)


def measurements(rows: Iterable[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    """A ``silver_measurements`` frame with clean defaults."""
    rows = list(rows or [{}])
    built = []
    for index, override in enumerate(rows, start=1):
        record = {
            "measurement_id": f"MS{index:04d}",
            "child_record_id": f"CR{index:04d}",
            "school_id": SCHOOL_ID,
            "period": "baseline",
            "measurement_date": pd.Timestamp("2024-09-01"),
            "age_years": 9.5,
            "height_cm": 124.3,
            "weight_kg": 23.7,
            "bmi": 15.3,
            "measurement_quality_flag": None,
        }
        record.update(override)
        built.append(record)

    frame = pd.DataFrame(built)
    frame["measurement_date"] = pd.to_datetime(frame["measurement_date"])
    for numeric in ("age_years", "height_cm", "weight_kg", "bmi"):
        frame[numeric] = frame[numeric].astype("float64")
    return SILVER_MEASUREMENTS.validate(frame)


def measurements_for(
    records: pd.DataFrame, heights: Mapping[str, float] | None = None
) -> pd.DataFrame:
    """Measurements matching an existing child-records frame, one row per record."""
    heights = heights or {}
    rows = [
        {
            "measurement_id": f"MS_{record_id}",
            "child_record_id": record_id,
            "school_id": school_id,
            "period": period,
            "height_cm": heights.get(record_id, 124.3),
        }
        for record_id, school_id, period in zip(
            records["child_record_id"],
            records["school_id"],
            records["period"],
            strict=True,
        )
    ]
    return measurements(rows)


def schools(rows: Iterable[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    """A ``silver_schools`` masterlist frame."""
    rows = list(rows or [{}])
    built = []
    for index, override in enumerate(rows, start=1):
        record = {
            "school_id": SCHOOL_ID if index == 1 else f"SCH_{index:03d}",
            "school_name": "Bubong Central Elementary School",
            "division": "Lanao del Sur II",
            "municipality": "Bubong",
            "barangay": "Poblacion",
            "urban_rural": "Rural",
            "treatment_status": 1,
            "matched_pair_id": "PAIR_01",
        }
        record.update(override)
        built.append(record)

    frame = pd.DataFrame(built)
    frame["treatment_status"] = frame["treatment_status"].astype("int64")
    return SILVER_SCHOOLS.validate(frame)


def allocations(rows: Iterable[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    """A ``silver_allocations`` frame."""
    rows = list(rows or [{}])
    built = []
    for index, override in enumerate(rows, start=1):
        record = {
            "school_id": SCHOOL_ID if index == 1 else f"SCH_{index:03d}",
            "school_year": "2024-2025",
            "allocated_children": 300.0,
            "current_enrollment": 280.0,
            "nominal_rice_kg_per_child": 0.09,
            "effective_rice_kg_per_child": 0.09,
            "dilution_ratio": 1.0,
            "delivery_tranche_count": 3.0,
            "delivery_timing_flag": "on_time",
        }
        record.update(override)
        built.append(record)

    frame = pd.DataFrame(built)
    for numeric in (
        "allocated_children",
        "current_enrollment",
        "nominal_rice_kg_per_child",
        "effective_rice_kg_per_child",
        "dilution_ratio",
        "delivery_tranche_count",
    ):
        frame[numeric] = frame[numeric].astype("float64")
    return SILVER_ALLOCATIONS.validate(frame)


def file_manifest(rows: Iterable[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    """A ``bronze_file_manifest`` frame."""
    rows = list(rows or [{}])
    built = []
    for index, override in enumerate(rows, start=1):
        record = {
            "source_file_id": SOURCE_FILE_ID if index == 1 else f"FILE_{index:03d}",
            "source_file_path": f"data/synthetic_raw/baseline/file_{index}.xlsx",
            "file_name": f"file_{index}.xlsx",
            "file_type": "xlsx",
            "dataset": "school_submission",
            "file_hash": "0" * 64,
            "file_size_bytes": 2048,
            "modified_at": pd.Timestamp("2024-09-20"),
            "discovered_at": pd.Timestamp("2024-09-21"),
            "ingested_at": INGESTED_AT,
            "school_id_guess": SCHOOL_ID,
            "period_guess": "baseline",
            "run_id": RUN_ID,
            "status": "ingested",
            "rows_read": 10,
            "rows_written": 10,
            "error_message": None,
        }
        record.update(override)
        built.append(record)

    frame = pd.DataFrame(built)
    frame["file_size_bytes"] = frame["file_size_bytes"].astype("int64")
    for count in ("rows_read", "rows_written"):
        frame[count] = frame[count].astype("int64")
    for stamp in ("modified_at", "discovered_at", "ingested_at"):
        frame[stamp] = pd.to_datetime(frame[stamp])
    return BRONZE_FILE_MANIFEST.validate(frame)


def schema_drift(rows: Iterable[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    """A ``bronze_schema_drift_log`` frame."""
    rows = list(rows or [{}])
    built = []
    for override in rows:
        record = {
            "run_id": RUN_ID,
            "source_file_id": SOURCE_FILE_ID,
            "dataset": "school_submission",
            "column_name_raw": "Kaarawan",
            "drift_type": "unmapped_column",
            "mapped_to": None,
            "detected_at": INGESTED_AT,
        }
        record.update(override)
        built.append(record)

    frame = pd.DataFrame(built)
    frame["detected_at"] = pd.to_datetime(frame["detected_at"])
    return BRONZE_SCHEMA_DRIFT_LOG.validate(frame)
