"""Record identity — the recipe slice 3 must reproduce exactly.

The answer key is keyed on ``record_id``. The ingester never sees the key, so the only
way the two sides meet is for both to derive the same identifier from the same
observable facts about a raw file. Those facts are the file's location and the row's
position in it. Nothing else — not a column value, not a timestamp, not the row's
content — enters the derivation, because every one of those can be corrupted by an
injected defect and would then disagree across the two sides.

**The recipe, verbatim.**

1. ``rel_path`` is the file's path relative to ``config.paths.raw_data_dir``, rendered
   with forward slashes (``Path.relative_to(raw_data_dir).as_posix()``). Example:
   ``"baseline/baseline_100003_20240930.xlsx"``.
2. ``source_file_id = stable_id(rel_path)`` — a 16-hex-character digest, no prefix.
3. ``source_row_number`` is the **1-based position of the data row within its sheet or
   CSV, counting data rows only**. The header occupies the physical first line and is
   *not* counted, so the first data row is ``1``. With ``pandas.read_excel`` /
   ``read_csv`` defaults this is ``df.index + 1``.
4. ``record_id = stable_id(source_file_id, source_row_number)`` — again 16 hex
   characters, no prefix. Note the first argument is the *digest*, not the path.

``stable_id`` is :func:`sbfp_platform.utils.hashing.stable_id`, which joins its parts
with ``"|"`` and takes the first 16 characters of the SHA-256 hex digest.

Two consequences worth stating because they constrain both slices:

* Inserting or removing a row shifts every ``record_id`` below it. The generator
  therefore finalizes row order — including injected duplicate rows — *before* it
  assigns any identifier.
* File-scoped defects (a drifted school name, a late submission) have no row, so the
  answer key records them against the ``source_file_id`` itself. A file-scoped DQA rule
  should emit its issue with ``record_id = source_file_id`` for the join to land.

School-period-scoped defects use :func:`school_period_id`; see its docstring.
"""

from __future__ import annotations

from pathlib import Path

from sbfp_platform.utils.hashing import stable_id


def relative_file_key(path: Path, raw_data_dir: Path) -> str:
    """Render the observable path key for a raw file: POSIX, relative to the raw root."""
    return path.relative_to(raw_data_dir).as_posix()


def source_file_id(path: Path, raw_data_dir: Path) -> str:
    """Identity of a raw source file. Step 2 of the recipe in the module docstring."""
    return stable_id(relative_file_key(path, raw_data_dir))


def record_id(file_id: str, row_number: int) -> str:
    """Identity of one raw data row. Step 4 of the recipe in the module docstring."""
    return stable_id(file_id, row_number)


def school_period_id(school_id: str, period: str) -> str:
    """Identity of a school-period aggregate.

    ``truth_defects.record_id`` is non-nullable, but ``digit_heaping`` is a property of
    a whole school-period rather than of one row. The generator therefore records it
    per affected row (so the configured rate stays a per-record rate), and this helper
    exists for any consumer that needs the aggregate key itself.
    """
    return stable_id(school_id, period, prefix="SP-")
