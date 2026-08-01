"""Reading the raw cell behind a silver value, and classifying the shape of a date. Use this rule as shown."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd

from sbfp_platform.utils.text import normalize_header

# Excel has a false leap day. This base still maps its later date codes the same way.
_EXCEL_ORIGIN = date(1899, 12, 30)

# A smaller code looks like a bare year, not a date. This span runs from 1954 to 2064,
# which is wide enough for these files.
_SERIAL_MIN = 20_000
_SERIAL_MAX = 60_000

_INT_LIKE = re.compile(r"^\d{4,6}(?:\.0+)?$")
_TIME_SUFFIX = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\s*(?:[AaPp]\.?[Mm]\.?)?$")
_ISO = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_TWO_PART_FIRST = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$")


@dataclass(frozen=True)
class DateShape:
    """What a raw date string looks like, independent of how load parsed it."""

    raw: str | None
    parsed: date | None
    rule_used: str
    ambiguous: bool = False
    excel_serial: bool = False
    timestamp_suffix: bool = False
    blank: bool = False
    alternatives: tuple[date, ...] = ()

    @property
    def unparseable(self) -> bool:
        return self.parsed is None and not self.blank

    @property
    def readings(self) -> tuple[date, ...]:
        """Every date this value could legitimately denote. Use this rule as shown. Use this rule as shown. Keep this rule in place."""
        if self.alternatives:
            return self.alternatives
        return (self.parsed,) if self.parsed is not None else ()


def _to_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _expand_year(value: int) -> int:
    """Two-digit years: 00-29 are 2000s, 30-99 are 1900s (the usual sheet pivot)."""
    if value >= 100:
        return value
    return 2000 + value if value <= 29 else 1900 + value


@lru_cache(maxsize=8192)
def classify_date(raw: Any) -> DateShape:
    """Sort one raw date cell."""
    if raw is None or raw is pd.NaT:
        return DateShape(raw=None, parsed=None, rule_used="blank", blank=True)
    # Pandas may use ``pd.NA`` for a blank. Treat all lone blank marks the same. This lets
    # the missing-data rule own a blank birth date and stops a second date alert.
    try:
        if bool(pd.isna(raw)):
            return DateShape(raw=None, parsed=None, rule_used="blank", blank=True)
    except (TypeError, ValueError):
        # This code should get one cell. If it gets a list, mark it as bad text instead
        # of failing while it checks for a blank.
        pass

    if isinstance(raw, pd.Timestamp):
        return DateShape(raw=raw.isoformat(), parsed=raw.date(), rule_used="datetime")
    if isinstance(raw, date):
        return DateShape(raw=raw.isoformat(), parsed=raw, rule_used="datetime")

    if isinstance(raw, int | float):
        serial = float(raw)
        if _SERIAL_MIN <= serial <= _SERIAL_MAX:
            return DateShape(
                raw=str(raw),
                parsed=_EXCEL_ORIGIN + timedelta(days=int(serial)),
                rule_used="excel_serial",
                excel_serial=True,
            )
        return DateShape(raw=str(raw), parsed=None, rule_used="unparseable")

    text = str(raw).strip()
    if not text or text.lower() in {"nan", "nat", "none", "null", "n/a", "-"}:
        return DateShape(raw=text or None, parsed=None, rule_used="blank", blank=True)

    # An Excel date code may reach us as text, such as "43262".
    if _INT_LIKE.fullmatch(text):
        serial = float(text)
        if _SERIAL_MIN <= serial <= _SERIAL_MAX:
            return DateShape(
                raw=text,
                parsed=_EXCEL_ORIGIN + timedelta(days=int(serial)),
                rule_used="excel_serial",
                excel_serial=True,
            )
        return DateShape(raw=text, parsed=None, rule_used="unparseable")

    # Some date text ends with a time, such as "2019-02-17 00:00:00". Check the date and
    # keep a flag for the time.
    timestamp_suffix = bool(_TIME_SUFFIX.search(text))
    body = text
    if timestamp_suffix:
        body = _TIME_SUFFIX.sub("", text).strip().rstrip("T").strip()
        if not body:
            return DateShape(raw=text, parsed=None, rule_used="unparseable")

    iso = _ISO.fullmatch(body)
    if iso:
        parsed = _to_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        return DateShape(
            raw=text,
            parsed=parsed,
            rule_used="iso" if parsed else "unparseable",
            timestamp_suffix=timestamp_suffix,
        )

    parts = _TWO_PART_FIRST.fullmatch(body)
    if parts:
        first, second, year = (
            int(parts.group(1)),
            int(parts.group(2)),
            _expand_year(int(parts.group(3))),
        )
        as_mdy = _to_date(year, first, second)
        as_dmy = _to_date(year, second, first)
        if as_mdy and as_dmy and as_mdy != as_dmy:
            # Both ways give real dates. Log the doubt; do not hide the choice (spec §6).
            return DateShape(
                raw=text,
                parsed=as_mdy,
                rule_used="ambiguous_dmy",
                ambiguous=True,
                timestamp_suffix=timestamp_suffix,
                alternatives=(as_mdy, as_dmy),
            )
        if as_mdy:
            return DateShape(
                raw=text, parsed=as_mdy, rule_used="mdy", timestamp_suffix=timestamp_suffix
            )
        if as_dmy:
            return DateShape(
                raw=text, parsed=as_dmy, rule_used="dmy", timestamp_suffix=timestamp_suffix
            )
        return DateShape(raw=text, parsed=None, rule_used="unparseable")

    return DateShape(
        raw=text, parsed=None, rule_used="unparseable", timestamp_suffix=timestamp_suffix
    )


def alias_map(schema_registry: dict[str, Any], dataset: str) -> dict[str, str]:
    """Map every clean source header for dataset to its set column."""
    columns = (schema_registry.get("datasets") or {}).get(dataset, {}).get("columns", {})
    mapping: dict[str, str] = {}
    for key, entry in columns.items():
        canonical = entry.get("canonical", key)
        for header in (key, canonical, *(entry.get("aliases") or [])):
            mapping[normalize_header(header)] = canonical
    return mapping


def raw_payload_values(
    payloads: pd.Series,
    canonical_field: str,
    schema_registry: dict[str, Any],
    dataset: str = "school_submission",
) -> pd.Series:
    """Pull the raw source cell for canonical_field out of raw_payload_json. Use this rule as shown. Use this rule as shown."""
    lookup = alias_map(schema_registry, dataset)
    wanted = {header for header, canonical in lookup.items() if canonical == canonical_field}

    def extract(payload: Any) -> str | None:
        if payload is None or not isinstance(payload, str) or not payload.strip():
            return None
        try:
            row = json.loads(payload)
        except (ValueError, TypeError):
            return None
        if not isinstance(row, dict):
            return None
        for key, value in row.items():
            if normalize_header(key) in wanted:
                if value is None:
                    return None
                text = str(value).strip()
                return text or None
        return None

    return payloads.map(extract)


def raw_or_canonical(
    df: pd.DataFrame,
    canonical_field: str,
    schema_registry: dict[str, Any],
    dataset: str = "school_submission",
) -> pd.Series:
    """Raw source cell for canonical_field, falling back to the silver column. Use this rule as shown."""
    if "raw_payload_json" in df.columns:
        raw = raw_payload_values(df["raw_payload_json"], canonical_field, schema_registry, dataset)
    else:
        raw = pd.Series([None] * len(df), index=df.index, dtype=object)

    if canonical_field in df.columns:
        fallback = df[canonical_field]
        raw = raw.where(raw.notna(), fallback)
    return raw
