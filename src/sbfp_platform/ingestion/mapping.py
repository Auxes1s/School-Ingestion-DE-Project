"""Alias mapping, schema-drift detection, and value normalization.

The alias registry (``configs/schema_registry.yml``) is the contract that lets slices 2
and 3 be built in parallel: the generator draws headers from the alias lists, the
ingester folds them back with :func:`~sbfp_platform.utils.text.normalize_header`.

Drift is handled the way TDS §14.3 requires — nothing is dropped:

* a header that maps to a canonical column becomes that column;
* a header that maps to nothing survives in ``raw_payload_json`` and is logged as
  ``unmapped_column``;
* a registry column with no header is logged as ``missing_required`` or
  ``missing_optional``;
* only an absent ``minimum_viable`` column fails the file.

The last rule is the whole point. A school that renames "Weight" to "Timbang ng Bata"
should cost one drift-log row, not a lost submission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sbfp_platform.utils.text import normalize_header

UNMAPPED_COLUMN = "unmapped_column"
MISSING_REQUIRED = "missing_required"
MISSING_OPTIONAL = "missing_optional"

#: The ``drift_type`` vocabulary declared by ``BRONZE_SCHEMA_DRIFT_LOG``.
DRIFT_TYPES = (UNMAPPED_COLUMN, MISSING_REQUIRED, MISSING_OPTIONAL)


@dataclass(frozen=True)
class DatasetSpec:
    """One dataset's slice of the schema registry, pre-folded for lookup.

    Attributes:
        name: Registry key, e.g. ``school_submission``.
        required: Registry field names that should be present.
        minimum_viable: Registry field names without which the file cannot be ingested.
        canonical_by_field: Registry field name → canonical column name.
        field_by_alias_key: Folded header → registry field name.
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
        """Canonical columns in registry order, de-duplicated."""
        seen: dict[str, None] = {}
        for canonical in self.canonical_by_field.values():
            seen.setdefault(canonical, None)
        return tuple(seen)


@dataclass(frozen=True)
class HeaderMapping:
    """The result of matching one sheet's headers against a :class:`DatasetSpec`.

    Attributes:
        field_by_index: Column position → registry field name, for mapped columns.
        canonical_by_index: Column position → canonical column name.
        unmapped_indices: Positions of headers the registry does not know.
        missing_required: Required registry fields with no header.
        missing_optional: Non-required registry fields with no header.
        missing_minimum_viable: Minimum-viable fields with no header. Non-empty means
            the file must fail.
    """

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
    """Fold the schema registry into lookup tables, once per run.

    Args:
        config: A loaded :class:`~sbfp_platform.config.Config`.

    Returns:
        Registry dataset name → :class:`DatasetSpec`.
    """
    specs: dict[str, DatasetSpec] = {}
    for name, entry in config.schema_registry["datasets"].items():
        canonical_by_field: dict[str, str] = {}
        field_by_alias_key: dict[str, str] = {}
        for field, field_spec in entry["columns"].items():
            canonical_by_field[field] = field_spec["canonical"]
            # The registry field name and its canonical name are themselves valid
            # headers: a file already written in canonical form must still map.
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
    """Union of folded headers across every dataset, for header-row detection."""
    return {key for spec in specs.values() for key in spec.field_by_alias_key}


def map_headers(headers: list[str], spec: DatasetSpec) -> HeaderMapping:
    """Match raw headers to canonical columns and record what did not line up.

    A repeated header maps once. The second occurrence is treated as unmapped rather
    than overwriting the first, so its values reach ``raw_payload_json`` instead of
    silently replacing the column that already claimed the name.
    """
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
    """Guess a dataset from headers alone, for files outside the known subdirectories.

    Returns the dataset whose alias pool the headers match best, or ``None`` when no
    dataset's minimum-viable columns are all present.
    """
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
    """Invert ``value_normalization`` into canonical column → folded value → target.

    ``{"sex": {"m": "Male", "lalaki": "Male", ...}}``. Applied on read, before any DQA
    rule runs, so rules never have to know that ``"M"``, ``"1"``, and ``"Lalaki"`` are
    the same answer.
    """
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
    """Map one cell to its canonical value, or return it untouched.

    An unrecognized value passes through unchanged. Flagging it is the DQA layer's job;
    quietly blanking it here would hide the defect the scorecard is meant to measure.
    """
    lookup = normalizers.get(column)
    if not lookup or not value:
        return value
    return lookup.get(_fold_value(value), value)


def _fold_value(value: object) -> str:
    return str(value).strip().casefold()
