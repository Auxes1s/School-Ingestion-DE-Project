"""Map raw headers and values while keeping all source data.

The file ``configs/schema_registry.yml`` lets the data maker and loader work on their
own. The maker picks from its header names. The loader folds each name to the same key.

TDS §14.3 says not to drop drift. A known header maps to its set field. An unknown one
stays in ``raw_payload_json`` and gets an ``unmapped_column`` log row. A field with no
header gets a ``missing_required`` or ``missing_optional`` row. The file fails only if a
``minimum_viable`` field is gone. Thus a new name for weight makes one log row, not a
lost school file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sbfp_platform.utils.text import normalize_header

UNMAPPED_COLUMN = "unmapped_column"
MISSING_REQUIRED = "missing_required"
MISSING_OPTIONAL = "missing_optional"

# These are the drift types allowed in ``BRONZE_SCHEMA_DRIFT_LOG``.
DRIFT_TYPES = (UNMAPPED_COLUMN, MISSING_REQUIRED, MISSING_OPTIONAL)


@dataclass(frozen=True)
class DatasetSpec:
    """Store one data set's folded field map.

    Attributes:
        name: The map key, such as ``school_submission``.
        required: Fields that should be in the file.
        minimum_viable: Fields the file must have to load.
        canonical_by_field: Map each set field to its column name.
        field_by_alias_key: Map each folded header to its set field.
    """

    name: str
    required: tuple[str, ...]
    minimum_viable: tuple[str, ...]
    canonical_by_field: dict[str, str]
    field_by_alias_key: dict[str, str]

    @property
    def alias_keys(self) -> set[str]:
        return set(self.field_by_alias_key)

    @property
    def canonical_columns(self) -> tuple[str, ...]:
        """Set columns in rule list order, de-copied. Use this rule as shown."""
        seen: dict[str, None] = {}
        for canonical in self.canonical_by_field.values():
            seen.setdefault(canonical, None)
        return tuple(seen)


@dataclass(frozen=True)
class HeaderMapping:
    """The result of matching one sheet's headers against a DatasetSpec. Use this rule as shown."""

    field_by_index: dict[int, str]
    canonical_by_index: dict[int, str]
    unmapped_indices: tuple[int, ...]
    missing_required: tuple[str, ...]
    missing_optional: tuple[str, ...]
    missing_minimum_viable: tuple[str, ...]

    @property
    def is_viable(self) -> bool:
        return not self.missing_minimum_viable


def build_dataset_specs(config: Any) -> dict[str, DatasetSpec]:
    """Fold the schema rule list into lookup tables, once per run."""
    specs: dict[str, DatasetSpec] = {}
    for name, entry in config.schema_registry["datasets"].items():
        canonical_by_field: dict[str, str] = {}
        field_by_alias_key: dict[str, str] = {}
        for field, field_spec in entry["columns"].items():
            canonical_by_field[field] = field_spec["canonical"]
            # The rule name and set name are both valid headers. A clean file must still map.
            for alias in (*field_spec["aliases"], field, field_spec["canonical"]):
                field_by_alias_key.setdefault(normalize_header(alias), field)
        specs[name] = DatasetSpec(
            name=name,
            required=tuple(entry.get("required") or ()),
            minimum_viable=tuple(entry.get("minimum_viable") or ()),
            canonical_by_field=canonical_by_field,
            field_by_alias_key=field_by_alias_key,
        )
    return specs


def all_alias_keys(specs: dict[str, DatasetSpec]) -> set[str]:
    """Union of folded headers across every dataset, for header-row detection. Use this rule as shown. Use this rule as shown. Keep this rule in place."""
    return {key for spec in specs.values() for key in spec.field_by_alias_key}


def map_headers(headers: list[str], spec: DatasetSpec) -> HeaderMapping:
    """Match raw headers to set columns and record what did not line up."""
    field_by_index: dict[int, str] = {}
    canonical_by_index: dict[int, str] = {}
    unmapped: list[int] = []
    claimed: set[str] = set()

    for index, header in enumerate(headers):
        field = spec.field_by_alias_key.get(normalize_header(header))
        if field is None or field in claimed:
            unmapped.append(index)
            continue
        claimed.add(field)
        field_by_index[index] = field
        canonical_by_index[index] = spec.canonical_by_field[field]

    present = set(field_by_index.values())
    known = set(spec.canonical_by_field)
    missing_required = tuple(f for f in spec.required if f not in present)
    missing_optional = tuple(sorted(known - present - set(spec.required)))
    missing_minimum_viable = tuple(f for f in spec.minimum_viable if f not in present)

    return HeaderMapping(
        field_by_index=field_by_index,
        canonical_by_index=canonical_by_index,
        unmapped_indices=tuple(unmapped),
        missing_required=missing_required,
        missing_optional=missing_optional,
        missing_minimum_viable=missing_minimum_viable,
    )


def classify_by_headers(headers: list[str], specs: dict[str, DatasetSpec]) -> str | None:
    """Guess a dataset from headers alone, for files outside the known subfolders. Use this rule as shown."""
    keys = {normalize_header(header) for header in headers}
    best: tuple[int, str] | None = None
    for name, spec in specs.items():
        mapping = map_headers(headers, spec)
        if not mapping.is_viable:
            continue
        score = len(keys & spec.alias_keys)
        if best is None or score > best[0]:
            best = (score, name)
    return best[1] if best else None


# --------------------------------------------------------------------------------------
# Value normalization
# --------------------------------------------------------------------------------------


def build_value_normalizers(config: Any) -> dict[str, dict[str, str]]:
    """Invert value_normalization into set column to folded value to target. Use this rule as shown. Use this rule as shown. Keep this rule in place."""
    normalizers: dict[str, dict[str, str]] = {}
    for column, mapping in (config.schema_registry.get("value_normalization") or {}).items():
        lookup: dict[str, str] = {}
        for target, variants in mapping.items():
            for variant in variants:
                lookup[_fold_value(variant)] = str(target)
            lookup.setdefault(_fold_value(target), str(target))
        normalizers[column] = lookup
    return normalizers


def normalize_value(column: str, value: str, normalizers: dict[str, dict[str, str]]) -> str:
    """Map one cell to its set value, or return it untouched."""
    lookup = normalizers.get(column)
    if not lookup or not value:
        return value
    return lookup.get(_fold_value(value), value)


def _fold_value(value: object) -> str:
    return str(value).strip().casefold()
