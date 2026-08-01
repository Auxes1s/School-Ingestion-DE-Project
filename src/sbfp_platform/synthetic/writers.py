"""Write the same raw file bytes for the same seed and size.

Spec §7 calls for an exact match. For CSV, pin new lines, text form, and quote rules.
An XLSX is a ZIP file. Its parts and ``docProps/core.xml`` get the wall clock by default.
Build the book in memory, then set a fixed ZIP time and change time. If this is skipped,
the same run can yield new bytes and make the test fail at random.
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

# Put this fixed time in each book. The date has no other use.
FIXED_DOC_TIMESTAMP = dt.datetime(2020, 1, 1, 0, 0, 0)

# Use the first time ZIP can store for each part.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

_AUTHOR = "sbfp-platform synthetic generator"

_MODIFIED_TAG = re.compile(r"<dcterms:modified[^>]*>[^<]*</dcterms:modified>")
_FIXED_MODIFIED_TAG = (
    '<dcterms:modified xsi:type="dcterms:W3CDTF">2020-01-01T00:00:00Z</dcterms:modified>'
)

CellValue = str | int | float | dt.date | None


def write_csv(path: Path, header: list[str], rows: list[list[CellValue]]) -> None:
    """Save a CSV with pinned encoding, newline, and quoting. Use this rule as shown."""
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
        # Keep it short and fixed: write 121.4, not a long float tail.
        return f"{value:g}"
    return str(value)


def write_xlsx(path: Path, sheet_name: str, header: list[str], rows: list[list[CellValue]]) -> None:
    """Save a single-sheet workbook whose bytes depend only on its contents. Use this rule as shown."""
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
    """Rewrite an XLSX archive with fixed entry timestamps and a fixed modified stamp. Use this rule as shown."""
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
    """Dispatch on file_type ("xlsx" or "csv"). Use this rule as shown."""
    if file_type == "xlsx":
        write_xlsx(path, sheet_name, header, rows)
    elif file_type == "csv":
        write_csv(path, header, rows)
    else:  # pragma: no cover - guarded by the config contract
        raise ValueError(f"Unsupported file type {file_type!r}; expected 'xlsx' or 'csv'.")
