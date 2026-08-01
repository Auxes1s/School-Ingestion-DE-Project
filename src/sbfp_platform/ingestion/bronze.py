"""Store bronze Parquet parts and track each file version.

The folder shape follows TDS §14.5. Each source file gets one part. If its hash has not
changed, the load step does not open it or write its rows again.

Two lists serve two needs. ``file_manifest/`` keeps the latest row for each path, as the
table shape asks. ``file_manifest_history/`` keeps all old rows, even rows marked
``superseded``, as TDS §14.2 asks. This keeps the live list valid and the full trail safe.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from sbfp_platform.contracts import BRONZE_FILE_MANIFEST, BRONZE_SCHEMA_DRIFT_LOG

MANIFEST_DIR = "file_manifest"
MANIFEST_HISTORY_DIR = "file_manifest_history"
DRIFT_LOG_DIR = "schema_drift_log"
INGESTION_ERRORS_DIR = "ingestion_errors"
SUPERSEDED_DIR = "_superseded"

STATUS_INGESTED = "ingested"
STATUS_SKIPPED = "skipped_unchanged"
STATUS_FAILED = "failed"
STATUS_SUPERSEDED = "superseded"

MANIFEST_COLUMNS = tuple(BRONZE_FILE_MANIFEST.columns)
DRIFT_LOG_COLUMNS = tuple(BRONZE_SCHEMA_DRIFT_LOG.columns)

_MANIFEST_DATETIME_COLUMNS = ("modified_at", "discovered_at", "ingested_at")
_MANIFEST_INT_COLUMNS = ("file_size_bytes", "rows_read", "rows_written")
_DRIFT_DATETIME_COLUMNS = ("detected_at",)

ERROR_LOG_COLUMNS = (
    "run_id",
    "source_file_id",
    "source_file_path",
    "dataset",
    "error_type",
    "error_message",
    "detected_at",
)


# --------------------------------------------------------------------------------------
# Frame shaping
# --------------------------------------------------------------------------------------


def build_manifest_frame(rows: list[dict]) -> pd.DataFrame:
    """Shape manifest rows into a frame that passes its checks against BRONZE_FILE_MANIFEST. Use this rule as shown. Use this rule as shown."""
    frame = _frame(rows, MANIFEST_COLUMNS)
    for column in _MANIFEST_DATETIME_COLUMNS:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    for column in _MANIFEST_INT_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype("int64")
    return frame


def build_drift_frame(rows: list[dict]) -> pd.DataFrame:
    """Shape drift rows into a frame that passes its checks against BRONZE_SCHEMA_DRIFT_LOG."""
    frame = _frame(rows, DRIFT_LOG_COLUMNS)
    for column in _DRIFT_DATETIME_COLUMNS:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def build_error_frame(rows: list[dict]) -> pd.DataFrame:
    frame = _frame(rows, ERROR_LOG_COLUMNS)
    frame["detected_at"] = pd.to_datetime(frame["detected_at"], errors="coerce")
    return frame


def normalize_nulls(frame: pd.DataFrame) -> pd.DataFrame:
    """Force every missing value in a text column to None. Use this rule as shown."""
    for column in frame.columns:
        if frame[column].dtype == object:
            frame[column] = pd.Series(
                [None if _is_null(value) else value for value in frame[column]],
                index=frame.index,
                dtype=object,
            )
    return frame


def _is_null(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):  # arrays and lists are never a scalar null
        return False


def _frame(rows: list[dict], columns: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=list(columns))
    for column in columns:
        if column not in frame:
            frame[column] = None
    return normalize_nulls(frame[list(columns)])


# --------------------------------------------------------------------------------------
# Part files
# --------------------------------------------------------------------------------------


def write_part(directory: Path, name: str, frame: pd.DataFrame) -> Path:
    """Write one parquet part, replacing any part of the same name."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.parquet"
    frame.to_parquet(target, index=False)
    return target


def unique_part_name(directory: Path, base: str) -> str:
    """A part name that cannot clobber an existing part. Use this rule as shown."""
    if not (directory / f"{base}.parquet").exists():
        return base
    index = 2
    while (directory / f"{base}__{index}.parquet").exists():
        index += 1
    return f"{base}__{index}"


def read_parts(directory: Path, columns: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Load every part in a bronze table folder. Use this rule as shown."""
    parts = sorted(directory.glob("*.parquet")) if directory.is_dir() else []
    if not parts:
        return pd.DataFrame(columns=list(columns)) if columns else pd.DataFrame()
    frames = [pd.read_parquet(part) for part in parts]
    return normalize_nulls(pd.concat(frames, ignore_index=True))


def supersede_part(directory: Path, name: str, file_hash: str) -> Path | None:
    """Move a part out of the active table, keeping it for audit.

    Returns the archived path, or ``None`` if there was nothing to move.
    """
    source = directory / f"{name}.parquet"
    if not source.is_file():
        return None
    archive = directory / SUPERSEDED_DIR
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / f"{name}__{file_hash[:8]}.parquet"
    shutil.move(str(source), str(target))
    return target


# --------------------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------------------


def read_manifest_history(bronze_dir: Path) -> pd.DataFrame:
    """The append-only manifest history, oldest first. Use this rule as shown. Use this rule as shown. Keep this rule in place."""
    frame = read_parts(bronze_dir / MANIFEST_HISTORY_DIR, MANIFEST_COLUMNS)
    if frame.empty:
        return build_manifest_frame([])
    return frame


def write_manifest(bronze_dir: Path, history: pd.DataFrame) -> tuple[Path, Path]:
    """Persist the history and the contract-valid current snapshot derived from it. Use this rule as shown. Use this rule as shown."""
    history = build_manifest_frame(history.to_dict("records"))
    history_path = write_part(bronze_dir / MANIFEST_HISTORY_DIR, "history", history)
    snapshot = current_manifest(history)
    manifest_path = write_part(bronze_dir / MANIFEST_DIR, "manifest", snapshot)
    return history_path, manifest_path


def current_manifest(history: pd.DataFrame) -> pd.DataFrame:
    """Latest row per source_file_id. one row per file, as the contract requires."""
    if history.empty:
        return build_manifest_frame([])
    latest = history.drop_duplicates(subset="source_file_id", keep="last").reset_index(drop=True)
    return build_manifest_frame(latest.to_dict("records"))
