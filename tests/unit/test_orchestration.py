from __future__ import annotations

from orchestration.dagster_project.definitions import defs


def test_dagster_asset_graph_captures_cross_framework_order() -> None:
    graph = defs.resolve_asset_graph()
    names = {key.to_user_string() for key in graph.get_all_asset_keys()}
    assert names == {
        "synthetic_source_files",
        "bronze_layer",
        "silver_layer",
        "dqa_issue_registry",
        "linkage_results",
        "gold_layer",
        "measured_scorecards",
        "public_exports",
    }

    parents = {
        key.to_user_string(): {
            parent.key.to_user_string() for parent in graph.get_parents(graph.get(key))
        }
        for key in graph.get_all_asset_keys()
    }
    assert parents["silver_layer"] == {"bronze_layer"}
    assert parents["dqa_issue_registry"] == {"silver_layer"}
    assert parents["linkage_results"] == {"silver_layer"}
    assert parents["gold_layer"] == {"dqa_issue_registry", "linkage_results"}


def test_dagster_jobs_resolve() -> None:
    names = {job.name for job in defs.resolve_all_job_defs()}
    assert {"full_refresh_job", "quality_job", "reporting_job"} <= names
