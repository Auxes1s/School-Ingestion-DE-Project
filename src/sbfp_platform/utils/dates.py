"""Date parsing for messy school-submission spreadsheets.

A port of the real LDS II ``standardize_birthday()`` behavior (spec §6, TDS §14.4).
Schools submit the same field as an Excel serial, a US-style ``MM/DD/YYYY``, a
Philippine-style ``DD/MM/YYYY``, an ISO string with a midnight timestamp glued on, a
two-digit year, or a blank. The parser accepts all of them.

The one thing it never does is silently pick a winner. ``01/02/2019`` is a real date
under both ``MM/DD`` and ``DD/MM``; this module resolves it the way the real pipeline
does — month first — but records ``confidence < 1.0`` and ``issue_flag="ambiguous_dmy"``
so the DQA layer can count how much of the panel rests on a coin flip.

``parsed_date is not None`` is the single test for "usable". A value that parses cleanly
but lands outside the plausible-year window is rejected: ``parsed_date`` is ``None`` and
``issue_flag`` is ``"out_of_range"``, while ``rule_used`` still names the rule that
matched, so a reviewer can see what it would have been.

Rule vocabulary
---------------
``rule_used`` is a base rule plus optional modifiers, in order:

``<base>[_yy][_ts]``

* ``_yy`` — the year was written with two digits and expanded about
  :data:`TWO_DIGIT_YEAR_PIVOT`.
* ``_ts`` — a time-of-day suffix was stripped before parsing.

Bases: ``blank``, ``date_value``, ``excel_serial``, ``excel_serial_string``,
``ymd_compact``, ``iso``, ``ymd_slash``, ``ymd_dot``, ``mdy_slash``, ``mdy_dash``,
``mdy_dot``, ``dmy_slash``, ``dmy_dash``, ``dmy_dot``, ``month_name``, ``unparseable``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# --------------------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------------------

#: Excel's day-zero on Windows. Serial 1 is 1899-12-31.
EXCEL_EPOCH = date(1899, 12, 30)

#: Serials outside this band are not dates, they are numbers that happen to be in a date
#: column. 2958465 is 9999-12-31.
MIN_EXCEL_SERIAL = 1
MAX_EXCEL_SERIAL = 2_958_465

#: Absolute sanity window, used when the caller does not supply a tighter one. Callers
#: parsing birthdays pass ``configs/project.yml:birth_year_min``/``birth_year_max``.
DEFAULT_MIN_YEAR = 1900
DEFAULT_MAX_YEAR = 2100

#: Two-digit years at or below this map to the 2000s, above it to the 1900s. Matches the
#: Excel and ``strptime`` convention, so ``"19"`` is 2019 and ``"98"`` is 1998.
TWO_DIGIT_YEAR_PIVOT = 68

AMBIGUOUS_DMY = "ambiguous_dmy"
OUT_OF_RANGE = "out_of_range"
UNPARSEABLE = "unparseable"
MISSING = "missing"

#: The closed set of ``issue_flag`` values. ``None`` means a clean parse.
ISSUE_FLAGS = (AMBIGUOUS_DMY, OUT_OF_RANGE, UNPARSEABLE, MISSING)

#: Confidence assigned when ``DD/MM`` and ``MM/DD`` both yield a real date.
AMBIGUOUS_CONFIDENCE = 0.5

#: Values that mean "the school left this blank", not "the school wrote garbage".
BLANK_TOKENS = frozenset(
    {"", "-", "--", "---", ".", "?", "n/a", "na", "n.a.", "null", "none", "nan", "#n/a", "#null!"}
)

_SEPARATOR_RULES = {"/": "slash", "-": "dash", ".": "dot"}

_TRIPLE = re.compile(r"^(\d{1,4})([/\-.])(\d{1,2})\2(\d{1,4})$")
_NUMERIC = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_TIMESTAMP = re.compile(
    r"[ T]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\s*(?:[AaPp]\.?[Mm]\.?)?\s*(?:Z|[+-]\d{2}:?\d{2})?$"
)

_MONTH_NAME_FORMATS = (
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%d-%b-%y",
    "%b %d %Y",
    "%B %d %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b, %Y",
)


@dataclass(frozen=True)
class ParsedDate:
    """The outcome of one parse attempt.

    Attributes:
        raw_value: The source text, stripped. ``""`` for blanks and nulls.
        parsed_date: The resolved date, or ``None`` if the value is blank, unparseable,
            or outside the plausible-year window.
        rule_used: Which rule matched. Populated even when ``parsed_date`` is ``None``
            because of the year guard.
        confidence: ``1.0`` for an unambiguous parse, :data:`AMBIGUOUS_CONFIDENCE` when
            day and month could be swapped, ``0.0`` when nothing usable came out.
        issue_flag: One of :data:`ISSUE_FLAGS`, or ``None`` for a clean parse.
    """

    raw_value: str
    parsed_date: date | None
    rule_used: str
    confidence: float
    issue_flag: str | None

    @property
    def is_usable(self) -> bool:
        """True when a date came out. Ambiguous dates are usable but low confidence."""
        return self.parsed_date is not None

    @property
    def iso(self) -> str | None:
        """The parsed date as ``YYYY-MM-DD``, or ``None``."""
        return self.parsed_date.isoformat() if self.parsed_date else None


# --------------------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------------------


def parse_date(
    value: object,
    *,
    min_year: int | None = DEFAULT_MIN_YEAR,
    max_year: int | None = DEFAULT_MAX_YEAR,
) -> ParsedDate:
    """Parse one spreadsheet cell into a :class:`ParsedDate`.

    Args:
        value: Anything a reader can hand back — ``str``, ``int``, ``float``,
            ``datetime``, ``date``, ``None``, or ``float('nan')``.
        min_year: Lower bound of the plausible-year window, or ``None`` for no bound.
            Birthday columns pass ``configs/project.yml:birth_year_min``.
        max_year: Upper bound, or ``None`` for no bound.

    Returns:
        A :class:`ParsedDate`. Never raises for bad input; unparseable values come back
        with ``parsed_date=None`` and ``issue_flag="unparseable"``.
    """
    raw = _raw_text(value)

    if _is_blank(value, raw):
        return ParsedDate(raw, None, "blank", 0.0, MISSING)

    # A reader that already resolved the cell to a date (openpyxl does this for
    # date-formatted cells) needs no parsing, only the range guard.
    if isinstance(value, datetime):
        return _finalize(value.date(), raw, "date_value", 1.0, None, min_year, max_year)
    if isinstance(value, date):
        return _finalize(value, raw, "date_value", 1.0, None, min_year, max_year)

    if isinstance(value, bool):
        return ParsedDate(raw, None, "unparseable", 0.0, UNPARSEABLE)

    # A true numeric cell can only be an Excel serial.
    if isinstance(value, (int, float)):
        resolved = _from_serial(float(value))
        if resolved is None:
            return ParsedDate(raw, None, "unparseable", 0.0, UNPARSEABLE)
        return _finalize(resolved, raw, "excel_serial", 1.0, None, min_year, max_year)

    text, stripped_timestamp = _strip_timestamp(raw)
    suffix = "_ts" if stripped_timestamp else ""

    if not text:
        return ParsedDate(raw, None, "blank", 0.0, MISSING)

    # A number written into a text column: "43262", or "43262.0" after a round trip
    # through a float.
    if _NUMERIC.match(text):
        compact = _from_compact_ymd(text)
        if compact is not None:
            return _finalize(compact, raw, f"ymd_compact{suffix}", 1.0, None, min_year, max_year)
        resolved = _from_serial(float(text))
        if resolved is None:
            return ParsedDate(raw, None, "unparseable", 0.0, UNPARSEABLE)
        return _finalize(
            resolved, raw, f"excel_serial_string{suffix}", 1.0, None, min_year, max_year
        )

    triple = _parse_numeric_triple(text)
    if triple is not None:
        resolved, base, confidence, flag = triple
        return _finalize(resolved, raw, f"{base}{suffix}", confidence, flag, min_year, max_year)

    named = _parse_month_name(text)
    if named is not None:
        return _finalize(named, raw, f"month_name{suffix}", 1.0, None, min_year, max_year)

    return ParsedDate(raw, None, "unparseable", 0.0, UNPARSEABLE)


# --------------------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------------------


def _raw_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _is_blank(value: object, raw: str) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return raw.lower() in BLANK_TOKENS


def _strip_timestamp(text: str) -> tuple[str, bool]:
    """Remove a trailing time-of-day, as in ``"2019-02-17 00:00:00"``."""
    stripped = _TIMESTAMP.sub("", text).strip()
    return (stripped, True) if stripped != text else (text, False)


def _make_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _expand_two_digit_year(value: int) -> int:
    return 2000 + value if value <= TWO_DIGIT_YEAR_PIVOT else 1900 + value


def _from_serial(number: float) -> date | None:
    """Convert an Excel serial to a date, or ``None`` if it is not a plausible serial."""
    if math.isnan(number) or math.isinf(number):
        return None
    if not MIN_EXCEL_SERIAL <= number <= MAX_EXCEL_SERIAL:
        return None
    return EXCEL_EPOCH + timedelta(days=int(number))


def _from_compact_ymd(text: str) -> date | None:
    """Parse ``YYYYMMDD``. Eight-digit values are never plausible Excel serials."""
    if len(text) != 8 or not text.isdigit():
        return None
    year, month, day = int(text[:4]), int(text[4:6]), int(text[6:8])
    if not DEFAULT_MIN_YEAR <= year <= DEFAULT_MAX_YEAR:
        return None
    return _make_date(year, month, day)


def _parse_numeric_triple(text: str) -> tuple[date, str, float, str | None] | None:
    """Resolve ``A<sep>B<sep>C`` into a date plus the rule that produced it.

    Returns ``(date, base_rule, confidence, issue_flag)``, or ``None`` if the text is not
    a numeric triple or no ordering of it is a real date.
    """
    match = _TRIPLE.match(text)
    if match is None:
        return None

    first, separator, middle, last = match.groups()
    separator_rule = _SEPARATOR_RULES[separator]

    # Year first: unambiguous by construction.
    if len(first) == 4:
        resolved = _make_date(int(first), int(middle), int(last))
        if resolved is None:
            return None
        base = "iso" if separator == "-" else f"ymd_{separator_rule}"
        return resolved, base, 1.0, None

    if len(last) == 4:
        year, year_suffix = int(last), ""
    elif len(last) <= 2:
        year, year_suffix = _expand_two_digit_year(int(last)), "_yy"
    else:
        return None

    a, b = int(first), int(middle)
    as_mdy = _make_date(year, a, b)
    as_dmy = _make_date(year, b, a)

    if as_mdy is not None and as_dmy is not None:
        rule = f"mdy_{separator_rule}{year_suffix}"
        # 05/05/2019 is the same day under either reading, so nothing is at stake.
        if a == b:
            return as_mdy, rule, 1.0, None
        # Month-first wins, matching the real pipeline's precedence — but the coin flip
        # is recorded rather than resolved away.
        return as_mdy, rule, AMBIGUOUS_CONFIDENCE, AMBIGUOUS_DMY
    if as_mdy is not None:
        return as_mdy, f"mdy_{separator_rule}{year_suffix}", 1.0, None
    if as_dmy is not None:
        return as_dmy, f"dmy_{separator_rule}{year_suffix}", 1.0, None
    return None


def _parse_month_name(text: str) -> date | None:
    """Parse spelled-out months, as in ``"17 Feb 2019"``."""
    candidate = " ".join(text.split())
    for fmt in _MONTH_NAME_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def _finalize(
    resolved: date,
    raw: str,
    rule: str,
    confidence: float,
    flag: str | None,
    min_year: int | None,
    max_year: int | None,
) -> ParsedDate:
    """Apply the plausible-year guard to a successful parse."""
    if (min_year is not None and resolved.year < min_year) or (
        max_year is not None and resolved.year > max_year
    ):
        return ParsedDate(raw, None, rule, 0.0, OUT_OF_RANGE)
    return ParsedDate(raw, resolved, rule, confidence, flag)
