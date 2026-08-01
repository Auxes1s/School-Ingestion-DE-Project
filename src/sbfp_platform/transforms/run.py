"""Run dbt and write files that are safe to share.

Silver and gold are split by design. Row links and data checks run between them. dbt
owns the set-based changes. This file sets run paths and saves DuckDB tables as Parquet.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
from dbt.cli.main import dbtRunner, dbtRunnerResult

from sbfp_platform.contracts import FORBIDDEN_GOLD_COLUMNS
from sbfp_platform.utils.logging import get_logger

logger = get_logger(__name__)

SILVER_MODELS = (
    "silver_child_records",
    "silver_measurements",
    "silver_schools",
    "silver_allocations",
)

GOLD_MODELS = (
    "gold_evaluation_child_panel",
    "gold_school_monitoring_mart",
    "gold_dqa_command_center",
    "gold_linkage_review_mart",
    "gold_program_exposure_mart",
    "gold_public_dashboard_metrics",
)


@dataclass(frozen=True)
class TransformResult:
    """Saved model names and their easy-to-move parquet copies. Use this rule as shown."""

    models: tuple[str, ...]
    parquet_paths: tuple[Path, ...]


class DbtBuildError(RuntimeError):
    """Raised when dbt cannot compile, run, or test a selected layer. Use this rule as shown."""


def _dbt_vars(config: Any) -> dict[str, str | float]:
    bronze = config.paths.bronze_dir
    return {
        "bronze_school_submissions": str(bronze / "school_submissions"),
        "bronze_school_masterlist": str(bronze / "school_masterlist"),
        "bronze_enrollment_snapshots": str(bronze / "enrollment_snapshots"),
        "bronze_program_allocations": str(bronze / "program_allocations"),
        "dqa_issues_path": str(config.paths.silver_dir / "silver_dqa_issues.parquet"),
        "linkage_results_path": str(config.paths.linkage_dir / "silver_linkage_results.parquet"),
        "linkage_candidates_path": str(
            config.paths.linkage_dir / "silver_linkage_candidates.parquet"
        ),
        "nominal_rice_kg_per_child": float(config.synthetic["nominal_rice_kg_per_child"]),
    }


def _run_dbt(config: Any, selector: str, *, indirect_selection: str = "cautious") -> None:
    project_dir = config.paths.root / "dbt"
    args = [
        "build",
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(project_dir),
        "--select",
        selector,
        "--indirect-selection",
        indirect_selection,
        "--vars",
        _yaml_inline(_dbt_vars(config)),
    ]
    old_path = os.environ.get("SBFP_DUCKDB_PATH")
    os.environ["SBFP_DUCKDB_PATH"] = str(config.paths.duckdb_path)
    try:
        result: dbtRunnerResult = dbtRunner().invoke(args)
    finally:
        if old_path is None:
            os.environ.pop("SBFP_DUCKDB_PATH", None)
        else:
            os.environ["SBFP_DUCKDB_PATH"] = old_path
    if not result.success:
        detail = f": {result.exception}" if result.exception else ""
        raise DbtBuildError(f"dbt build failed for {selector}{detail}")


def _yaml_inline(values: dict[str, str | float]) -> str:
    """turn dbt vars without adding a PyYAML tool to this boundary."""
    import json

    return json.dumps(values)


def _copy_models(config: Any, models: Iterable[str], directory: Path) -> tuple[Path, ...]:
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with duckdb.connect(str(config.paths.duckdb_path)) as connection:
        for model in models:
            destination = directory / f"{model}.parquet"
            connection.execute(
                f'copy (select * from "main"."{model}") to {_sql_string(destination)} '
                "(format parquet, compression zstd, overwrite true)",
            )
            paths.append(destination)
    return tuple(paths)


def build_silver(config: Any) -> TransformResult:
    """Make/test silver in DuckDB and publish contract-aligned parquet tables. Use this rule as shown. Use this rule as shown."""
    config.paths.ensure()
    _run_dbt(config, "tag:silver")
    paths = _copy_models(config, SILVER_MODELS, config.paths.silver_dir)
    logger.info("Built %d silver models in %s", len(paths), config.paths.silver_dir)
    return TransformResult(SILVER_MODELS, paths)


def build_gold(config: Any) -> TransformResult:
    """Make/test gold after DQA and linkage, then publish safe parquet. Use this rule as shown."""
    config.paths.ensure()
    # The gold panel's school relationship test spans a gold child and its silver
    # parent. Buildable selection runs that cross-layer test without rebuilding silver.
    _run_dbt(config, "tag:gold", indirect_selection="buildable")
    _assert_no_forbidden_columns(config, GOLD_MODELS)
    paths = _copy_models(config, GOLD_MODELS, config.paths.gold_dir)
    logger.info("Built %d gold models in %s", len(paths), config.paths.gold_dir)
    return TransformResult(GOLD_MODELS, paths)


def _assert_no_forbidden_columns(config: Any, models: Iterable[str]) -> None:
    forbidden = set(FORBIDDEN_GOLD_COLUMNS)
    with duckdb.connect(str(config.paths.duckdb_path)) as connection:
        for model in models:
            columns = {
                row[0]
                for row in connection.execute(f'describe select * from "main"."{model}"').fetchall()
            }
            found = columns & forbidden
            if found:
                raise RuntimeError(f"Privacy check failed for {model}: {sorted(found)}")


def build_exports(config: Any) -> TransformResult:
    """Export every serving mart in both CSV and Parquet, plus a data dictionary. Use this rule as shown. Use this rule as shown."""
    config.paths.ensure()
    config.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    # dbt keeps a read and write link open in this process. A read-only link here would
    # clash with it in a full run.
    with duckdb.connect(str(config.paths.duckdb_path)) as connection:
        available = {
            row[0]
            for row in connection.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        missing = set(GOLD_MODELS) - available
        if missing:
            raise FileNotFoundError(
                "Cannot export before gold is built; missing DuckDB table(s): "
                + ", ".join(sorted(missing))
            )

        for model in GOLD_MODELS:
            public_name = model.removeprefix("gold_")
            for suffix, options in (
                ("parquet", "format parquet, compression zstd, overwrite true"),
                ("csv", "format csv, header true, overwrite true"),
            ):
                destination = config.paths.exports_dir / f"{public_name}.{suffix}"
                connection.execute(
                    f'copy (select * from "main"."{model}") '
                    f"to {_sql_string(destination)} ({options})",
                )
                written.append(destination)

        dictionary = config.paths.exports_dir / "data_dictionary.csv"
        model_literals = ", ".join(_sql_string(model) for model in GOLD_MODELS)
        connection.execute(
            "copy (select table_name, column_name, data_type, is_nullable, ordinal_position "
            "from information_schema.columns where table_schema = 'main' "
            f"and table_name in ({model_literals}) order by table_name, ordinal_position) "
            f"to {_sql_string(dictionary)} (format csv, header true, overwrite true)",
        )
        written.append(dictionary)

    _scan_export_headers(written)
    logger.info("Wrote %d public exports to %s", len(written), config.paths.exports_dir)
    return TransformResult(GOLD_MODELS, tuple(written))


def _scan_export_headers(paths: Iterable[Path]) -> None:
    """Fail closed if a private column reaches a public file. Use this rule as shown."""
    forbidden = set(FORBIDDEN_GOLD_COLUMNS)
    for path in paths:
        if path.suffix == ".parquet":
            import pyarrow.parquet as pq

            columns = set(pq.read_schema(path).names)
        else:
            with path.open(newline="", encoding="utf-8") as handle:
                columns = set(next(csv.reader(handle), []))
        found = columns & forbidden
        if found:
            raise RuntimeError(f"Privacy check failed for export {path.name}: {sorted(found)}")


def _sql_string(value: str | Path) -> str:
    """Quote a trusted local path/model literal for DuckDB COPY syntax. Use this rule as shown. Use this rule as shown. Keep this rule in place."""
    return "'" + str(value).replace("'", "''") + "'"
