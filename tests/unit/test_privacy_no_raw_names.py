"""Private fields must not survive into gold or the shared files."""

from __future__ import annotations

import pytest

from sbfp_platform.config import load_config
from sbfp_platform.contracts import FORBIDDEN_GOLD_COLUMNS

GOLD_SCHEMAS = [
    "GOLD_EVALUATION_CHILD_PANEL",
    "GOLD_DQA_SCORECARD",
    "GOLD_LINKAGE_SCORECARD",
]


@pytest.mark.parametrize("schema_name", GOLD_SCHEMAS)
def test_declared_gold_schema_excludes_identifying_columns(schema_name: str) -> None:
    import sbfp_platform.contracts as contracts

    schema = getattr(contracts, schema_name)
    offenders = set(schema.columns) & set(FORBIDDEN_GOLD_COLUMNS)
    assert not offenders, (
        f"{schema_name} declares identifying column(s) {sorted(offenders)}. "
        "Gold must not carry names or raw learner identifiers."
    )


def test_materialized_gold_tables_exclude_identifying_columns() -> None:
    """Runtime counterpart: check what was actually written, not just what was declared. This keeps the test fair. It must work as shown."""
    import pyarrow.parquet as pq

    cfg = load_config()
    gold_dir = cfg.paths.gold_dir
    if not gold_dir.is_dir():
        pytest.skip("gold layer not built")

    files = list(gold_dir.rglob("*.parquet"))
    if not files:
        pytest.skip("gold layer not built")

    offenders: dict[str, list[str]] = {}
    for path in files:
        columns = set(pq.read_schema(path).names)
        found = sorted(columns & set(FORBIDDEN_GOLD_COLUMNS))
        if found:
            offenders[str(path.relative_to(cfg.paths.root))] = found

    assert not offenders, f"Identifying columns present in gold: {offenders}"


def test_exports_exclude_identifying_columns() -> None:
    import csv

    import pyarrow.parquet as pq

    cfg = load_config()
    exports = cfg.paths.exports_dir
    if not exports.is_dir():
        pytest.skip("exports not built")

    offenders: dict[str, list[str]] = {}
    for path in exports.rglob("*"):
        if path.suffix == ".parquet":
            columns = set(pq.read_schema(path).names)
        elif path.suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as handle:
                header = next(csv.reader(handle), [])
            columns = set(header)
        else:
            continue
        found = sorted(columns & set(FORBIDDEN_GOLD_COLUMNS))
        if found:
            offenders[str(path.relative_to(cfg.paths.root))] = found

    assert not offenders, f"Identifying columns present in exports: {offenders}"
