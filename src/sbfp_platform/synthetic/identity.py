"""Set the one ID rule that the data maker and loader must share.

The truth uses ``record_id``, but the loader cannot see the truth. Both sides must make
the same ID from facts they can see: the file path and row place. Do not use cell data,
file time, or row bytes. A test flaw can change any of those.

Use this exact rule:

1. Get the file path from ``config.paths.raw_data_dir`` and use POSIX slashes.
2. Make ``source_file_id = stable_id(rel_path)`` with 16 hex chars and no prefix.
3. Count data rows from one. Do not count the header.
4. Make ``record_id = stable_id(source_file_id, source_row_number)``. Pass the ID from
   step two, not the path.

``stable_id`` joins its parts with ``|`` and keeps the first 16 chars of the SHA-256
hash. Set row order before IDs. If a row is added or cut, all IDs below it move.

A file flaw has no row, so it uses ``source_file_id`` as ``record_id``. A flaw tied to a
school and wave uses :func:`school_period_id`.
"""

from __future__ import annotations

from pathlib import Path

from sbfp_platform.utils.hashing import stable_id


def relative_file_key(path: Path, raw_data_dir: Path) -> str:
    """Render the seen path key for a raw file: POSIX, relative to the raw root."""
    return path.relative_to(raw_data_dir).as_posix()


def source_file_id(path: Path, raw_data_dir: Path) -> str:
    """ID of a raw raw file."""
    return stable_id(relative_file_key(path, raw_data_dir))


def record_id(file_id: str, row_number: int) -> str:
    """ID of one raw data row."""
    return stable_id(file_id, row_number)


def school_period_id(school_id: str, period: str) -> str:
    """ID of a school-period group."""
    return stable_id(school_id, period, prefix="SP-")
