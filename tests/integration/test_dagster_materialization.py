from __future__ import annotations

import pytest
from dagster import materialize
from orchestration.dagster_project.definitions import ALL_ASSETS

pytestmark = pytest.mark.integration


def test_dagster_materializes_the_full_tiny_asset_graph(monkeypatch) -> None:
    monkeypatch.setenv("SBFP_PROFILE", "tiny")
    result = materialize(ALL_ASSETS)
    assert result.success
    materialized = {
        event.asset_key.to_user_string()
        for event in result.get_asset_materialization_events()
        if event.asset_key is not None
    }
    assert materialized == {asset.key.to_user_string() for asset in ALL_ASSETS}
