"""Dagster definitions for the complete, cross-framework asset graph."""

import os

from dagster import (
    Definitions,
    MaterializeResult,
    ScheduleDefinition,
    asset,
    define_asset_job,
)

from sbfp_platform.config import load_config


def _config():
    """Resolve the profile at execution time, not import time."""
    return load_config(profile=os.environ.get("SBFP_PROFILE"))


@asset(group_name="source", description="Generate messy synthetic source files and answer keys.")
def synthetic_source_files() -> MaterializeResult:
    from sbfp_platform.synthetic.generate import generate_all

    cfg = _config()
    result = generate_all(cfg)
    return MaterializeResult(
        metadata={"profile": cfg.profile, "schools": cfg.scale["schools"], "result": str(result)}
    )


@asset(deps=[synthetic_source_files], group_name="lakehouse")
def bronze_layer() -> MaterializeResult:
    from sbfp_platform.ingestion.run import run_ingestion

    result = run_ingestion(_config())
    return MaterializeResult(
        metadata={
            "files_ingested": result.files_ingested,
            "files_skipped": result.files_skipped,
            "rows_written": result.rows_written,
        }
    )


@asset(deps=[bronze_layer], group_name="lakehouse")
def silver_layer() -> MaterializeResult:
    from sbfp_platform.transforms.run import build_silver

    build_silver(_config())
    return MaterializeResult(metadata={"stage": "dbt silver"})


@asset(deps=[silver_layer], group_name="quality")
def dqa_issue_registry() -> MaterializeResult:
    from sbfp_platform.validation.run import run_dqa

    issues = run_dqa(_config())
    return MaterializeResult(metadata={"issues": len(issues)})


@asset(deps=[silver_layer], group_name="linkage")
def linkage_results() -> MaterializeResult:
    from sbfp_platform.linkage.run import run_linkage

    result = run_linkage(_config())
    count = len(result) if hasattr(result, "__len__") else 0
    return MaterializeResult(metadata={"rows": count})


@asset(deps=[dqa_issue_registry, linkage_results], group_name="lakehouse")
def gold_layer() -> MaterializeResult:
    from sbfp_platform.transforms.run import build_gold

    build_gold(_config())
    return MaterializeResult(metadata={"stage": "dbt gold"})


@asset(deps=[gold_layer], group_name="evaluation")
def measured_scorecards() -> MaterializeResult:
    from sbfp_platform.evaluation.run import build_scorecards

    result = build_scorecards(_config())
    return MaterializeResult(metadata={"result": str(result)})


@asset(deps=[measured_scorecards], group_name="serving")
def public_exports() -> MaterializeResult:
    from sbfp_platform.transforms.run import build_exports

    result = build_exports(_config())
    return MaterializeResult(metadata={"result": str(result)})


ALL_ASSETS = [
    synthetic_source_files,
    bronze_layer,
    silver_layer,
    dqa_issue_registry,
    linkage_results,
    gold_layer,
    measured_scorecards,
    public_exports,
]

full_refresh_job = define_asset_job("full_refresh_job", selection="*")
quality_job = define_asset_job(
    "quality_job",
    selection=["synthetic_source_files", "bronze_layer", "silver_layer", "dqa_issue_registry"],
)
reporting_job = define_asset_job(
    "reporting_job", selection=["gold_layer", "measured_scorecards", "public_exports"]
)

weekly_refresh = ScheduleDefinition(job=full_refresh_job, cron_schedule="0 6 * * 1")

defs = Definitions(
    assets=ALL_ASSETS,
    jobs=[full_refresh_job, quality_job, reporting_job],
    schedules=[weekly_refresh],
)
