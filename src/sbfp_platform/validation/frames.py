"""Loading the tables the rule engine evaluates.

Validation reads the lakehouse; it never reads a source spreadsheet and never reaches
into another slice's Python. Two frames are mandatory — without child records and
measurements there is nothing to validate. The rest are optional: the school masterlist,
the allocation table, the bronze manifest and the drift log each unlock a subset of
rules, and their absence downgrades those rules to "skipped", never to a crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pandera.pandas import DataFrameSchema

from sbfp_platform.contracts import (
    BRONZE_FILE_MANIFEST,
    BRONZE_SCHEMA_DRIFT_LOG,
    SILVER_ALLOCATIONS,
    SILVER_CHILD_RECORDS,
    SILVER_MEASUREMENTS,
    SILVER_SCHOOLS,
)

CHILD_RECORDS = "child_records"
MEASUREMENTS = "measurements"
SCHOOLS = "schools"
ALLOCATIONS = "allocations"
FILE_MANIFEST = "file_manifest"
SCHEMA_DRIFT = "schema_drift"


class MissingSilverError(FileNotFoundError):
    """A frame the rule engine cannot run without is not in the lakehouse."""


@dataclass(frozen=True)
class FrameSource:
    """Where one frame lives and whether the engine can proceed without it."""

    name: str
    layer: str
    table: str
    schema: DataFrameSchema
    required: bool

    def candidates(self, directory: Path) -> list[Path]:
        """Accept both ``<table>.parquet`` and a partitioned ``<table>/`` directory.

        dbt-duckdb writes either shape depending on materialization, and validation
        should not care which one slice 5 settles on. Bronze metadata is physically
        stored without the logical ``bronze_`` prefix (for example
        ``file_manifest/manifest.parquet``), so both logical and physical names are
        accepted here.
        """
        found: list[Path] = []
        names = [self.table]
        if self.layer == "bronze" and self.table.startswith("bronze_"):
            names.append(self.table.removeprefix("bronze_"))
        for name in names:
            single = directory / f"{name}.parquet"
            if single.is_file():
                found.append(single)
            partitioned = directory / name
            if partitioned.is_dir():
                found.extend(sorted(partitioned.rglob("*.parquet")))
        return found


FRAME_SOURCES: tuple[FrameSource, ...] = (
    FrameSource(CHILD_RECORDS, "silver", "silver_child_records", SILVER_CHILD_RECORDS, True),
    FrameSource(MEASUREMENTS, "silver", "silver_measurements", SILVER_MEASUREMENTS, True),
    FrameSource(SCHOOLS, "silver", "silver_schools", SILVER_SCHOOLS, False),
    FrameSource(ALLOCATIONS, "silver", "silver_allocations", SILVER_ALLOCATIONS, False),
    FrameSource(FILE_MANIFEST, "bronze", "bronze_file_manifest", BRONZE_FILE_MANIFEST, False),
    FrameSource(SCHEMA_DRIFT, "bronze", "bronze_schema_drift_log", BRONZE_SCHEMA_DRIFT_LOG, False),
)


def _directory_for(config, layer: str) -> Path:
    return config.paths.silver_dir if layer == "silver" else config.paths.bronze_dir


def load_frames(config) -> dict[str, pd.DataFrame]:
    """Read every available input frame from the lakehouse.

    Raises:
        MissingSilverError: if a required frame is absent, with the commands that
            produce it.
    """
    frames: dict[str, pd.DataFrame] = {}
    missing_required: list[str] = []

    for source in FRAME_SOURCES:
        directory = _directory_for(config, source.layer)
        paths = source.candidates(directory)
        if not paths:
            if source.required:
                missing_required.append(f"{source.table} (expected under {directory})")
            continue
        frames[source.name] = pd.concat(
            [pd.read_parquet(path) for path in paths], ignore_index=True
        )

    if missing_required:
        raise MissingSilverError(
            "Cannot run DQA: required table(s) not found — "
            + "; ".join(missing_required)
            + ". Build the lakehouse first: `sbfp-platform generate-demo-data`, "
            "`sbfp-platform ingest`, then `sbfp-platform build-silver`."
        )
    return frames
