"""Reading the raw cell behind a silver value, and classifying the shape of a date.

Two problems this module solves for the rule set:

**Raw values.** The date rules cannot work from ``birthday_str`` alone: by the time a
row reaches silver the date has been normalized, so the evidence of an Excel serial or a
DD/MM vs MM/DD ambiguity is gone. Every silver row carries ``raw_payload_json`` (the
bronze provenance contract, spec §11.1), which holds the source row keyed by its
original spreadsheet header. Resolving that header through the alias registry in
``configs/schema_registry.yml`` recovers the raw cell without depending on any column
the ingestion slice may or may not add.

**Date shape.** :func:`classify_date` is a classifier, not a parser: it answers "what
kind of date string is this" so a rule can decide whether to raise an issue. The
ingestion slice owns the authoritative parse (spec §6); this is deliberately a second,
independent read of the same string, which is what lets validation disagree with
ingestion instead of rubber-stamping it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd

from sbfp_platform.utils.text import normalize_header

#: Excel's day-zero on Windows. Serial 1 is 1900-01-01, with the 1900 leap-year bug
#: baked in, which this origin reproduces for every date after 1900-03-01.
_EXCEL_ORIGIN = date(1899, 12, 30)

#: Serial values narrower than this look like bare years ("2019") rather than dates.
#: 20000..60000 spans 1954-10-03 to 2064-04-08 — wide enough for any plausible cell.
_SERIAL_MIN = 20_000
_SERIAL_MAX = 60_000

_INT_LIKE = re.compile(r"^\d{4,6}(?:\.0+)?$")
_TIME_SUFFIX = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\s*(?:[AaPp]\.?[Mm]\.?)?$")
_ISO = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_TWO_PART_FIRST = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$")


@dataclass(frozen=True)
class DateShape:
    """What a raw date string looks like, independent of how ingestion parsed it.

    Attributes:
        raw: The string as it appeared in the source cell.
        parsed: Best-effort date, or ``None`` when nothing plausible could be read.
        rule_used: Which pattern matched — ``excel_serial``, ``iso``, ``dmy``, ``mdy``,
            ``ambiguous_dmy``, ``blank``, or ``unparseable``.
        ambiguous: The value parses under both DD/MM and MM/DD to different dates.
        excel_serial: The cell held a serial number instead of a date.
        timestamp_suffix: The cell held a date with a time component appended.
        blank: The cell was empty. Completeness rules own this case, not date rules.
    """

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
        """Every date this value could legitimately denote.

        One entry for an unambiguous value, two for a DD/MM vs MM/DD ambiguity. Callers
        comparing two dates should intersect readings rather than compare ``parsed``:
        two spreadsheets writing the same day in different conventions are not a
        disagreement about the day.
        """
        if self.alternatives:
            return self.alternatives
        return (self.parsed,) if self.parsed is not None else ()


def _to_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _expand_year(value: int) -> int:
    """Two-digit years: 00-29 are 2000s, 30-99 are 1900s (the usual spreadsheet pivot)."""
    if value >= 100:
        return value
    return 2000 + value if value <= 29 else 1900 + value


@lru_cache(maxsize=8192)
def classify_date(raw: Any) -> DateShape:
    """Classify one raw date cell.

    Pure and memoized: the same string always yields the same classification, and school
    submissions repeat date formats heavily, so the cache pays for itself.
    """
    if raw is None or raw is pd.NaT:
        return DateShape(raw=None, parsed=None, rule_used="blank", blank=True)
    # Pandas' nullable dtypes use ``pd.NA`` rather than float NaN. Treat every
    # scalar missing sentinel alike so a nullable-string birth date is owned by
    # the completeness rule and is not double-counted as an impossible date.
    try:
        if bool(pd.isna(raw)):
            return DateShape(raw=None, parsed=None, rule_used="blank", blank=True)
    except (TypeError, ValueError):
        # ``classify_date`` is called on cells, but retain a useful unparseable
        # result if a non-scalar value reaches it instead of failing in null
        # detection.
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

    # Excel serial that survived as a string, e.g. "43262".
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

    # Timestamp-suffixed strings, e.g. "2019-02-17 00:00:00". Classify the date part and
    # carry the suffix flag through.
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
            # Genuinely ambiguous: both readings are valid dates. Record it; do not
            # silently pick one (spec §6).
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
    """Map every normalized source header for ``dataset`` to its canonical column.

    Built from ``configs/schema_registry.yml``, the same registry the ingester maps with,
    so a header the ingester recognized is a header this module recognizes.
    """
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
    """Pull the raw source cell for ``canonical_field`` out of ``raw_payload_json``.

    Returns a string Series aligned to ``payloads``, with ``None`` where the payload is
    absent, unparseable, or carries no header mapping to the field.
    """
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
    """Raw source cell for ``canonical_field``, falling back to the silver column.

    The fallback matters for two reasons: a row may carry no payload, and the unit
    fixtures for date rules are easier to read when the raw value can be written directly
    into ``birthday_str``.
    """
    if "raw_payload_json" in df.columns:
        raw = raw_payload_values(df["raw_payload_json"], canonical_field, schema_registry, dataset)
    else:
        raw = pd.Series([None] * len(df), index=df.index, dtype=object)

    if canonical_field in df.columns:
        fallback = df[canonical_field]
        raw = raw.where(raw.notna(), fallback)
    return raw
