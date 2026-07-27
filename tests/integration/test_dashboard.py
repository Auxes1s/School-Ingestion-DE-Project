from __future__ import annotations

import shutil

from streamlit.testing.v1 import AppTest

from sbfp_platform.config import repo_root


def test_dashboard_renders_all_views_without_exceptions(tmp_path, monkeypatch) -> None:
    source_root = repo_root()
    shutil.copytree(source_root / "configs", tmp_path / "configs")
    monkeypatch.setenv("SBFP_REPO_ROOT", str(tmp_path))
    app = AppTest.from_file(str(source_root / "dashboards" / "streamlit_app.py")).run(timeout=30)
    assert not app.exception
    assert len(app.tabs) == 6
