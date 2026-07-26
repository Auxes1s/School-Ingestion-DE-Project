"""Text normalization shared by the generator, the ingester, and the linkage layer.

``normalize_header`` is the definition referenced by ``configs/schema_registry.yml``.
Alias lists in that file must be distinct *under this function* — a rule enforced by
tests/unit/test_config_contracts.py, so the registry cannot drift into ambiguity.
"""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_header(value: str) -> str:
    """Fold a spreadsheet column header to its comparison key.

    Lowercases, strips accents, and collapses every run of non-alphanumeric characters
    to a single space. ``"SCHOOL_ID"``, ``"School ID"``, and ``"school  id"`` all fold to
    ``"school id"``.
    """
    folded = unicodedata.normalize("NFKD", str(value))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = _NON_ALNUM.sub(" ", folded.lower())
    return folded.strip()


def normalize_name(value: str | None) -> str | None:
    """Standardize a learner name for comparison and blocking.

    Uppercases, strips accents and punctuation, and collapses whitespace. Mirrors the
    real pipeline's ``standardize_name`` contract, whose output feeds both
    ``student_name_clean`` and the ``first_letter_name`` blocking key.
    """
    if value is None:
        return None
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z\s'-]", " ", text)
    text = _WHITESPACE.sub(" ", text).strip().upper()
    return text or None


def first_letter(name: str | None) -> str | None:
    """Blocking key: first character of the standardized name."""
    normalized = normalize_name(name)
    return normalized[0] if normalized else None
