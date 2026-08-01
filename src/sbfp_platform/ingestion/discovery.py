"""Find raw files and work out what each one holds.

This follows TDS §14.1. Each bronze row and file list gets the same source facts.
``source_file_id`` is based on the POSIX path from the raw data root, not on file bytes.
A fixed path thus keeps its ID after a fix. A new hash can mark the old copy as replaced.
The data maker uses the same rule, so both sides get the same key on their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sbfp_platform.ingestion.mapping import DatasetSpec, classify_by_headers
from sbfp_platform.ingestion.readers import file_type_of, read_tables
from sbfp_platform.utils.hashing import file_hash, stable_id

# Map each raw folder to its data set. The folder is the main clue since a school may
# change a file name.
DATASET_BY_SUBDIR = {
    "baseline": "school_submission",
    "endline": "school_submission",
    "enrollment": "enrollment_snapshot",
    "allocation": "program_allocation",
    "reference": "school_masterlist",
}

# Map each data set to its bronze folder, as set by TDS §14.5.
BRONZE_TABLE_BY_DATASET = {
    "school_submission": "school_submissions",
    "enrollment_snapshot": "enrollment_snapshots",
    "program_allocation": "program_allocations",
    "school_masterlist": "school_masterlist",
}

# Use these words when a file sits outside a known folder.
_DATASET_KEYWORDS = (
    ("enrollment", "enrollment_snapshot"),
    ("enrolment", "enrollment_snapshot"),
    ("allocation", "program_allocation"),
    ("masterlist", "school_masterlist"),
    ("reference", "school_masterlist"),
    ("baseline", "school_submission"),
    ("endline", "school_submission"),
    ("submission", "school_submission"),
)

_PERIOD_KEYWORDS = (("baseline", "baseline"), ("endline", "endline"))

# A school ID found in a file name, such as ``SCH_0007_baseline.xlsx``.
_SCHOOL_ID_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])((?:SCH|SCHOOL|SID)[-_]?\d{2,})(?![0-9])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,8}[-_]?\d{3,})(?![0-9])"),
)

# Excel lock files and OS notes are not school files.
_IGNORED_PREFIXES = ("~$", ".")


@dataclass(frozen=True)
class DiscoveredFile:
    """One pair raw file with its ID and source facts."""

    path: Path
    relative_path: str
    source_file_id: str
    file_name: str
    file_type: str
    dataset: str
    file_hash: str
    file_size_bytes: int
    modified_at: datetime
    discovered_at: datetime
    school_id_guess: str | None
    period_guess: str | None

    @property
    def bronze_table(self) -> str:
        return BRONZE_TABLE_BY_DATASET[self.dataset]


def source_file_id_for(path: Path, raw_data_dir: Path) -> str:
    """The shared recipe: stable_id of the raw-root-relative POSIX path. Use this rule as shown. Use this rule as shown."""
    return stable_id(relative_posix(path, raw_data_dir))


def relative_posix(path: Path, root: Path) -> str:
    """Path relative to the repo root, with forward slashes. Use this rule as shown."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        # A file outside the repo has no short path, so use its full path as its ID.
        return resolved.as_posix()


def discover_files(config: Any, specs: dict[str, DatasetSpec]) -> list[DiscoveredFile]:
    """Walk the set raw subfolders and sort every readable file. Use this rule as shown."""
    root = config.paths.root
    raw_data_dir = config.paths.raw_data_dir
    discovered_at = datetime.now(UTC).replace(tzinfo=None)

    found: dict[str, DiscoveredFile] = {}
    for subdir_key, directory in config.paths.raw_subdirs.items():
        for path in _candidate_files(directory):
            record = _describe(path, root, raw_data_dir, subdir_key, specs, discovered_at)
            if record is not None:
                found.setdefault(record.relative_path, record)

        # These files sit in the raw root, not in a child folder.
    for path in _candidate_files(config.paths.raw_data_dir, recursive=False):
        record = _describe(path, root, raw_data_dir, None, specs, discovered_at)
        if record is not None:
            found.setdefault(record.relative_path, record)

    return [found[key] for key in sorted(found)]


def _candidate_files(directory: Path, *, recursive: bool = True) -> list[Path]:
    if not directory.is_dir():
        return []
    paths = directory.rglob("*") if recursive else directory.glob("*")
    return sorted(
        path
        for path in paths
        if path.is_file()
        and file_type_of(path) is not None
        and not path.name.startswith(_IGNORED_PREFIXES)
    )


def _describe(
    path: Path,
    root: Path,
    raw_data_dir: Path,
    subdir_key: str | None,
    specs: dict[str, DatasetSpec],
    discovered_at: datetime,
) -> DiscoveredFile | None:
    dataset = _classify(path, subdir_key, specs)
    if dataset is None:
        return None

    stats = path.stat()
    return DiscoveredFile(
        path=path,
        relative_path=relative_posix(path, root),
        source_file_id=source_file_id_for(path, raw_data_dir),
        file_name=path.name,
        file_type=file_type_of(path) or "",
        dataset=dataset,
        file_hash=file_hash(path),
        file_size_bytes=stats.st_size,
        modified_at=datetime.fromtimestamp(stats.st_mtime, tz=UTC).replace(tzinfo=None),
        discovered_at=discovered_at,
        school_id_guess=guess_school_id(path.stem),
        period_guess=guess_period(path, subdir_key),
    )


def _classify(path: Path, subdir_key: str | None, specs: dict[str, DatasetSpec]) -> str | None:
    """Folder, then filename, then headers. Use this rule as shown."""
    if subdir_key in DATASET_BY_SUBDIR:
        return DATASET_BY_SUBDIR[subdir_key]

    haystack = f"{path.parent.name}/{path.stem}".lower()
    for keyword, dataset in _DATASET_KEYWORDS:
        if keyword in haystack:
            return dataset

    try:
        tables = read_tables(path, {key for spec in specs.values() for key in spec.alias_keys})
    except Exception:  # noqa: BLE001 - an unreadable file is simply not classifiable here
        return None
    for table in tables:
        dataset = classify_by_headers(table.headers, specs)
        if dataset is not None:
            return dataset
    return None


def guess_school_id(stem: str) -> str | None:
    """Pull a school ID out of a filename, if one is written there."""
    for pattern in _SCHOOL_ID_PATTERNS:
        match = pattern.search(stem)
        if match:
            return match.group(1).upper().replace("-", "_")
    return None


def guess_period(path: Path, subdir_key: str | None) -> str | None:
    """Which wave a file belongs to: the subfolder, else a filename keyword. Use this rule as shown."""
    if subdir_key in ("baseline", "endline"):
        return subdir_key
    for haystack in (path.parent.name.lower(), path.stem.lower()):
        for keyword, period in _PERIOD_KEYWORDS:
            if keyword in haystack:
                return period
    return None
