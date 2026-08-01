"""Clean text in the same way for data make, load, and link steps.

The file ``configs/schema_registry.yml`` uses ``normalize_header`` as its one header
rule. Its name lists must stay distinct after that rule runs. A test guards this so one
raw header can never point to two fields.
"""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_header(value: str) -> str:
    """Fold a sheet header to the key used for a match.

    Use lower case, strip marks, and turn each run of non-word chars into one space.
    Thus ``"SCHOOL_ID"``, ``"School ID"``, and ``"school  id"`` all become
    ``"school id"``.
    """
    folded = unicodedata.normalize("NFKD", str(value))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = _NON_ALNUM.sub(" ", folded.lower())
    return folded.strip()


def normalize_name(value: str | None) -> str | None:
    """Clean a child name for row match and block steps.

    Use upper case, strip marks and signs, and merge white space. This matches the real
    flow. Its result feeds ``student_name_clean`` and the ``first_letter_name`` block key.
    """
    if value is None:
        return None
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z\s'-]", " ", text)
    text = _WHITESPACE.sub(" ", text).strip().upper()
    return text or None


def first_letter(name: str | None) -> str | None:
    """Blocking key: first character of the clean name."""
    normalized = normalize_name(name)
    return normalized[0] if normalized else None
