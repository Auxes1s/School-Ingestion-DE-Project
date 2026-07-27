"""Byte-deterministic emission of the messy source files.

Same seed and profile must produce byte-identical files (spec §7), which rules out
both libraries' defaults. A CSV is easy — pin the newline, encoding, and quoting. An
XLSX is a ZIP archive, and both the archive's per-entry timestamps and the
``dcterms:modified`` stamp inside ``docProps/core.xml`` are written from the wall
clock. So the workbook is built in memory and the archive is then rewritten with a
fixed epoch and a fixed modification stamp. Without that step the determinism test
fails on the second run of the same second-boundary, which is exactly the kind of
flake that erodes trust in a regression suite.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import Workbook

#: Fixed document timestamp baked into every workbook. Arbitrary but constant.
FIXED_DOC_TIMESTAMP = dt.datetime(2020, 1, 1, 0, 0, 0)

#: Earliest timestamp the ZIP format can represent. Used for every archive entry.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

_AUTHOR = "sbfp-platform synthetic generator"

_MODIFIED_TAG = re.compile(r"<dcterms:modified[^>]*>[^<]*</dcterms:modified>")
_FIXED_MODIFIED_TAG = (
    '<dcterms:modified xsi:type="dcterms:W3CDTF">2020-01-01T00:00:00Z</dcterms:modified>'
)

CellValue = str | int | float | dt.date | None


def write_csv(path: Path, header: list[str], rows: list[list[CellValue]]) -> None:
    """Write a CSV with pinned encoding, newline, and quoting."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if value is None else _csv_cell(value) for value in row])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer.getvalue().encode("utf-8"))


def _csv_cell(value: CellValue) -> str:
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, float):
        # Trailing-zero-free but stable: 121.4 not 121.40000000000001.
        return f"{value:g}"
    return str(value)


def write_xlsx(path: Path, sheet_name: str, header: list[str], rows: list[list[CellValue]]) -> None:
    """Write a single-sheet workbook whose bytes depend only on its contents."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(header)
    for row in rows:
        sheet.append(row)

    workbook.properties.creator = _AUTHOR
    workbook.properties.lastModifiedBy = _AUTHOR
    workbook.properties.created = FIXED_DOC_TIMESTAMP
    workbook.properties.modified = FIXED_DOC_TIMESTAMP

    raw = io.BytesIO()
    workbook.save(raw)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_normalize_archive(raw.getvalue()))


def _normalize_archive(raw: bytes) -> bytes:
    """Rewrite an XLSX archive with fixed entry timestamps and a fixed modified stamp."""
    source = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "docProps/core.xml":
                data = _MODIFIED_TAG.sub(_FIXED_MODIFIED_TAG, data.decode("utf-8")).encode("utf-8")
            entry = zipfile.ZipInfo(info.filename, date_time=_ZIP_EPOCH)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 0
            entry.external_attr = 0o600 << 16
            target.writestr(entry, data)
    return out.getvalue()


def write_table(
    path: Path,
    file_type: str,
    sheet_name: str,
    header: list[str],
    rows: list[list[Any]],
) -> None:
    """Dispatch on ``file_type`` (``"xlsx"`` or ``"csv"``)."""
    if file_type == "xlsx":
        write_xlsx(path, sheet_name, header, rows)
    elif file_type == "csv":
        write_csv(path, header, rows)
    else:  # pragma: no cover - guarded by the config contract
        raise ValueError(f"Unsupported file type {file_type!r}; expected 'xlsx' or 'csv'.")
