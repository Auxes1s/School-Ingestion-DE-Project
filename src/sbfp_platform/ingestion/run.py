"""Find, map, parse, and load raw files into bronze.

This is the start point for ``sbfp-platform ingest``. Three tested rules hold here.

First, TDS §14.2 says the same file must be a no-op. If its hash is known, leave its part
as is and write no rows. If a known path has new bytes, load it and mark the old row as
``superseded``.

Second, TDS §14.3 says not to lose odd fields. Keep unknown headers in
``raw_payload_json`` and log them in ``bronze_schema_drift_log``. Fail only when a
``minimum_viable`` field is gone.

Third, spec §6 says not to hide a date choice. Store the parse rule, score, and issue
flag next to each parsed date.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from sbfp_platform.contracts import BRONZE_METADATA_COLUMNS
from sbfp_platform.ingestion import bronze
from sbfp_platform.ingestion.discovery import DiscoveredFile, discover_files
from sbfp_platform.ingestion.mapping import (
    MISSING_OPTIONAL,
    MISSING_REQUIRED,
    UNMAPPED_COLUMN,
    DatasetSpec,
    HeaderMapping,
    all_alias_keys,
    build_dataset_specs,
    build_value_normalizers,
    map_headers,
    normalize_value,
)
from sbfp_platform.ingestion.readers import RawTable, cell_to_text, read_tables
from sbfp_platform.utils.dates import (
    DEFAULT_MAX_YEAR,
    DEFAULT_MIN_YEAR,
    ParsedDate,
    parse_date,
)
from sbfp_platform.utils.hashing import stable_id
from sbfp_platform.utils.logging import get_logger, new_run_id

logger = get_logger(__name__)

# Parse these set fields as birth dates. Use the tight year span in
# ``configs/project.yml``. A birth date in 1974 is a key-in flaw.
BIRTH_DATE_COLUMNS = ("birthday_str",)

# Parse these set fields as event dates. Use only a broad year check.
EVENT_DATE_COLUMNS = ("measurement_date",)

# Add these suffixes to show how each date was read.
DATE_SUFFIXES = ("_parsed", "_parse_rule", "_parse_confidence", "_issue_flag")

# Keep these bronze fields as well as the set and source fields. ``period`` and
# ``school_id`` come from the file path, not its cells. Silver still needs them.
EXTRA_RECORD_COLUMNS = (
    "record_id",
    "dataset",
    "period_guess",
    "school_id_guess",
    "source_header_row",
)


@dataclass
class IngestionResult:
    """What one load run did."""

    run_id: str
    files_discovered: int = 0
    files_ingested: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_superseded: int = 0
    rows_read: int = 0
    rows_written: int = 0
    drift_events: int = 0
    rows_by_table: dict[str, int] = field(default_factory=dict)

    @property
    def is_noop(self) -> bool:
        """True when the run wrote no bronze record rows. the safe reruns assertion."""
        return self.rows_written == 0


def run_ingestion(config: Any, force: bool = False) -> IngestionResult:
    """Load every raw raw file into the bronze layer. Use this rule as shown."""
    config.paths.ensure()
    bronze_dir = config.paths.bronze_dir
    run_id = new_run_id("ingest")
    started_at = datetime.now(UTC).replace(tzinfo=None)

    specs = build_dataset_specs(config)
    header_keys = all_alias_keys(specs)
    normalizers = build_value_normalizers(config)
    birth_window = (config.project["birth_year_min"], config.project["birth_year_max"])

    history_rows: list[dict] = bronze.read_manifest_history(bronze_dir).to_dict("records")
    ingested_versions = {
        (row["source_file_id"], row["file_hash"])
        for row in history_rows
        if row["status"] == bronze.STATUS_INGESTED
    }

    discovered = discover_files(config, specs)
    result = IngestionResult(run_id=run_id, files_discovered=len(discovered))
    drift_rows: list[dict] = []
    error_rows: list[dict] = []

    for source in discovered:
        if not force and (source.source_file_id, source.file_hash) in ingested_versions:
            history_rows.append(_skipped_manifest_row(source, history_rows, run_id))
            result.files_skipped += 1
            continue

        try:
            extracted = _extract(
                source,
                specs[source.dataset],
                header_keys,
                normalizers,
                birth_window,
                run_id,
                started_at,
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the run
            logger.warning("Ingestion failed for %s: %s", source.relative_path, exc)
            history_rows.append(
                _manifest_row(source, run_id, started_at, bronze.STATUS_FAILED, 0, 0, str(exc))
            )
            error_rows.append(_error_row(source, run_id, started_at, type(exc).__name__, str(exc)))
            result.files_failed += 1
            continue

        drift_rows.extend(extracted.drift)
        error_rows.extend(extracted.errors)
        result.rows_read += extracted.rows_read

        if not extracted.records:
            message = extracted.failure or "No viable rows found in any sheet."
            history_rows.append(
                _manifest_row(
                    source,
                    run_id,
                    started_at,
                    bronze.STATUS_FAILED,
                    extracted.rows_read,
                    0,
                    message,
                )
            )
            error_rows.append(_error_row(source, run_id, started_at, "no_viable_rows", message))
            result.files_failed += 1
            continue

        frame = _records_frame(extracted.records, specs[source.dataset])
        # Replace the old copy only after the new one can be read. A bad fix must not
        # remove the last good copy from the live table.
        result.files_superseded += _supersede_previous(bronze_dir, source, history_rows)
        bronze.write_part(bronze_dir / source.bronze_table, source.source_file_id, frame)

        history_rows.append(
            _manifest_row(
                source,
                run_id,
                started_at,
                bronze.STATUS_INGESTED,
                extracted.rows_read,
                len(frame),
                None,
            )
        )
        ingested_versions.add((source.source_file_id, source.file_hash))
        result.files_ingested += 1
        result.rows_written += len(frame)
        result.rows_by_table[source.bronze_table] = result.rows_by_table.get(
            source.bronze_table, 0
        ) + len(frame)

    drift_rows = _dedupe_drift(drift_rows)
    result.drift_events = len(drift_rows)
    _append_log(bronze_dir / bronze.DRIFT_LOG_DIR, run_id, bronze.build_drift_frame, drift_rows)
    _append_log(
        bronze_dir / bronze.INGESTION_ERRORS_DIR, run_id, bronze.build_error_frame, error_rows
    )
    bronze.write_manifest(bronze_dir, bronze.build_manifest_frame(history_rows))

    logger.info(
        "%s: %d discovered, %d ingested, %d skipped, %d failed, %d superseded, "
        "%d rows written, %d drift events",
        run_id,
        result.files_discovered,
        result.files_ingested,
        result.files_skipped,
        result.files_failed,
        result.files_superseded,
        result.rows_written,
        result.drift_events,
    )
    return result


def _append_log(directory: Path, run_id: str, builder: Any, rows: list[dict]) -> None:
    """Save one part of an append-only log, skipping the save when there is nothing. Use this rule as shown."""
    if not rows:
        return
    bronze.write_part(directory, bronze.unique_part_name(directory, run_id), builder(rows))


# --------------------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------------------


@dataclass
class _Extracted:
    records: list[dict] = field(default_factory=list)
    drift: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    rows_read: int = 0
    failure: str | None = None


def _extract(
    source: DiscoveredFile,
    spec: DatasetSpec,
    header_keys: set[str],
    normalizers: dict[str, dict[str, str]],
    birth_window: tuple[int, int],
    run_id: str,
    ingested_at: datetime,
) -> _Extracted:
    """Load one file into bronze records, collecting drift and per-sheet failures. Use this rule as shown."""
    extracted = _Extracted()
    tables = read_tables(source.path, header_keys)
    if not tables:
        extracted.failure = "File contains no readable sheet."
        return extracted

    viable_sheets = 0
    for table in tables:
        mapping = map_headers(table.headers, spec)
        if not mapping.is_viable:
            # A "Notes" or "Instructions" tab is normal. Failing the file over one is not.
            message = (
                f"Sheet {table.sheet_name or source.file_name!r} lacks minimum viable "
                f"column(s): {', '.join(mapping.missing_minimum_viable)}."
            )
            extracted.errors.append(
                _error_row(source, run_id, ingested_at, "sheet_not_viable", message)
            )
            continue

        viable_sheets += 1
        extracted.drift.extend(_drift_rows(source, spec, table, mapping, run_id, ingested_at))
        extracted.rows_read += len(table.rows)
        extracted.records.extend(
            _sheet_records(
                source, spec, table, mapping, normalizers, birth_window, run_id, ingested_at
            )
        )

    if viable_sheets == 0:
        extracted.failure = (
            f"No sheet in {source.file_name} carries the minimum viable columns "
            f"({', '.join(spec.minimum_viable)})."
        )
    return extracted


def _sheet_records(
    source: DiscoveredFile,
    spec: DatasetSpec,
    table: RawTable,
    mapping: HeaderMapping,
    normalizers: dict[str, dict[str, str]],
    birth_window: tuple[int, int],
    run_id: str,
    ingested_at: datetime,
) -> list[dict]:
    records: list[dict] = []

    row_number = 0
    for row in table.rows:
        texts = [cell_to_text(cell) for cell in row]
        if not any(texts):
            # The shared truth rule counts rows with data. A blank row must not shift the
            # IDs that come after it.
            continue
        row_number += 1

        record: dict[str, Any] = dict.fromkeys(spec.canonical_columns)
        for index, canonical in mapping.canonical_by_index.items():
            record[canonical] = normalize_value(canonical, texts[index], normalizers) or None

        for canonical in spec.canonical_columns:
            if canonical in BIRTH_DATE_COLUMNS or canonical in EVENT_DATE_COLUMNS:
                raw_cell = _cell_for(canonical, row, mapping)
                record.update(_date_columns(canonical, raw_cell, birth_window))

        record.update(
            {
                "run_id": run_id,
                # This matches the hidden truth key. Use only fixed source points, never
                # cell text that a flaw may change.
                "record_id": stable_id(source.source_file_id, row_number),
                "source_file_id": source.source_file_id,
                "source_file_path": source.relative_path,
                "source_sheet_name": table.sheet_name,
                "source_row_number": row_number,
                "file_hash": source.file_hash,
                "ingested_at": ingested_at,
                # Keep the full raw row, not just fields that failed to map. Bronze must
                # show what the school sent.
                "raw_payload_json": json.dumps(
                    dict(zip(table.headers, texts, strict=True)), ensure_ascii=False
                ),
                "dataset": source.dataset,
                "period_guess": source.period_guess,
                "school_id_guess": source.school_id_guess,
                "source_header_row": table.header_row_index,
            }
        )
        records.append(record)

    return records


def _cell_for(canonical: str, row: list[object], mapping: HeaderMapping) -> object:
    for index, name in mapping.canonical_by_index.items():
        if name == canonical:
            return row[index]
    return None


def _date_columns(
    canonical: str, raw_cell: object, birth_window: tuple[int, int]
) -> dict[str, Any]:
    """Parse one date cell into its four source columns."""
    if canonical in BIRTH_DATE_COLUMNS:
        parsed = parse_date(raw_cell, min_year=birth_window[0], max_year=birth_window[1])
    else:
        parsed = parse_date(raw_cell, min_year=DEFAULT_MIN_YEAR, max_year=DEFAULT_MAX_YEAR)
    return _spread(canonical, parsed)


def _spread(canonical: str, parsed: ParsedDate) -> dict[str, Any]:
    return {
        f"{canonical}_parsed": parsed.parsed_date,
        f"{canonical}_parse_rule": parsed.rule_used,
        f"{canonical}_parse_confidence": parsed.confidence,
        f"{canonical}_issue_flag": parsed.issue_flag,
    }


def _records_frame(records: list[dict], spec: DatasetSpec) -> pd.DataFrame:
    """Shape bronze records, with a stable column order across files of one dataset. Use this rule as shown."""
    columns: list[str] = []
    for canonical in spec.canonical_columns:
        columns.append(canonical)
        if canonical in BIRTH_DATE_COLUMNS or canonical in EVENT_DATE_COLUMNS:
            columns.extend(f"{canonical}{suffix}" for suffix in DATE_SUFFIXES)
    columns.extend(BRONZE_METADATA_COLUMNS)
    columns.extend(EXTRA_RECORD_COLUMNS)

    frame = pd.DataFrame(records, columns=columns)
    frame["source_row_number"] = frame["source_row_number"].astype("int64")
    frame["source_header_row"] = frame["source_header_row"].astype("int64")
    frame["ingested_at"] = pd.to_datetime(frame["ingested_at"])
    for column in columns:
        if column.endswith("_parsed"):
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
        elif column.endswith("_parse_confidence"):
            frame[column] = frame[column].astype("float64")
    return bronze.normalize_nulls(frame)


# --------------------------------------------------------------------------------------
# Drift
# --------------------------------------------------------------------------------------


def _drift_rows(
    source: DiscoveredFile,
    spec: DatasetSpec,
    table: RawTable,
    mapping: HeaderMapping,
    run_id: str,
    detected_at: datetime,
) -> list[dict]:
    def row(column_name_raw: str, drift_type: str, mapped_to: str | None) -> dict:
        return {
            "run_id": run_id,
            "source_file_id": source.source_file_id,
            "dataset": source.dataset,
            "column_name_raw": column_name_raw,
            "drift_type": drift_type,
            "mapped_to": mapped_to,
            "detected_at": detected_at,
        }

    rows = [row(table.headers[i], UNMAPPED_COLUMN, None) for i in mapping.unmapped_indices]
    rows += [row(f, MISSING_REQUIRED, spec.canonical_by_field[f]) for f in mapping.missing_required]
    rows += [row(f, MISSING_OPTIONAL, spec.canonical_by_field[f]) for f in mapping.missing_optional]
    return rows


def _dedupe_drift(rows: list[dict]) -> list[dict]:
    """One row per (file, column, drift type). Sheets within a file are not distinguished."""
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for entry in rows:
        key = (entry["source_file_id"], entry["column_name_raw"], entry["drift_type"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique


# --------------------------------------------------------------------------------------
# Manifest rows
# --------------------------------------------------------------------------------------


def _manifest_row(
    source: DiscoveredFile,
    run_id: str,
    ingested_at: datetime | None,
    status: str,
    rows_read: int,
    rows_written: int,
    error_message: str | None,
) -> dict:
    return {
        "source_file_id": source.source_file_id,
        "source_file_path": source.relative_path,
        "file_name": source.file_name,
        "file_type": source.file_type,
        "dataset": source.dataset,
        "file_hash": source.file_hash,
        "file_size_bytes": source.file_size_bytes,
        "modified_at": source.modified_at,
        "discovered_at": source.discovered_at,
        "ingested_at": ingested_at,
        "school_id_guess": source.school_id_guess,
        "period_guess": source.period_guess,
        "run_id": run_id,
        "status": status,
        "rows_read": rows_read,
        "rows_written": rows_written,
        "error_message": error_message,
    }


def _skipped_manifest_row(source: DiscoveredFile, history_rows: list[dict], run_id: str) -> dict:
    """A skip carries forward what the original load recorded, not zeros. Use this rule as shown. Use this rule as shown."""
    prior = _latest(history_rows, file_hash=source.file_hash, status=bronze.STATUS_INGESTED)
    return _manifest_row(
        source,
        run_id,
        prior["ingested_at"] if prior else None,
        bronze.STATUS_SKIPPED,
        int(prior["rows_read"]) if prior else 0,
        int(prior["rows_written"]) if prior else 0,
        None,
    )


def _error_row(
    source: DiscoveredFile,
    run_id: str,
    detected_at: datetime,
    error_type: str,
    error_message: str,
) -> dict:
    return {
        "run_id": run_id,
        "source_file_id": source.source_file_id,
        "source_file_path": source.relative_path,
        "dataset": source.dataset,
        "error_type": error_type,
        "error_message": error_message,
        "detected_at": detected_at,
    }


def _supersede_previous(bronze_dir: Path, source: DiscoveredFile, history_rows: list[dict]) -> int:
    """Retire earlier versions of this path before writing a new one. Use this rule as shown."""
    superseded = 0
    for row in history_rows:
        if row["source_file_id"] != source.source_file_id:
            continue
        if row["status"] != bronze.STATUS_INGESTED:
            continue
        if row["file_hash"] == source.file_hash:
            continue
        row["status"] = bronze.STATUS_SUPERSEDED
        bronze.supersede_part(
            bronze_dir / source.bronze_table, source.source_file_id, row["file_hash"]
        )
        superseded += 1
    return superseded


def _latest(rows: list[dict], **criteria: Any) -> dict | None:
    for row in reversed(rows):
        if all(row.get(key) == value for key, value in criteria.items()):
            return row
    return None
