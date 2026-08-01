from __future__ import annotations

from pathlib import Path

import pytest
from tools.readability_audit import (
    CoverageError,
    Result,
    comment_results,
    markdown_results,
    markdown_units,
    slide_results,
)


def test_markdown_units_keep_visible_copy_and_drop_code(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text(
        "# A clear title for this page\n\n"
        "The cat sat on the mat.\n\n"
        "| Note |\n|---|\n| The dog ran in the sun. |\n\n"
        "![A bird flew past the red sun](bird.png)\n\n"
        "```py\nrun_hard_task()\n```\n",
        encoding="utf-8",
    )
    text = [unit for _, unit in markdown_units(path)]
    assert text == [
        "Note",
        "The dog ran in the sun.",
        "A clear title for this page. The cat sat on the mat.",
        "A bird flew past the red sun",
    ]


def test_markdown_results_fail_when_readme_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text("The cat sat on the mat.", encoding="utf-8")
    with pytest.raises(CoverageError, match="README"):
        markdown_results(tmp_path, [path])


def test_comment_results_score_docstrings_and_comments(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    path = source / "sample.py"
    path.write_text(
        '"""The cat sat on the mat."""\n\n# The dog ran in the sun.\nVALUE = 1\n',
        encoding="utf-8",
    )
    results = comment_results(tmp_path, [path])
    assert {result.kind for result in results} == {"comment", "docstring"}
    assert all(result.passed for result in results)


def test_comment_results_fail_closed_on_bad_python(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    path = source / "bad.py"
    path.write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(CoverageError, match="Could not parse"):
        comment_results(tmp_path, [path])


def test_slide_results_require_source_and_pdf(tmp_path: Path) -> None:
    with pytest.raises(CoverageError, match="Beamer source"):
        slide_results(tmp_path, [])
    folder = tmp_path / "docs" / "showcase_deck"
    folder.mkdir(parents=True)
    source = folder / "deck.tex"
    source.write_text("\\documentclass{beamer}", encoding="utf-8")
    with pytest.raises(CoverageError, match="compiled PDF"):
        slide_results(tmp_path, [source])


def test_result_uses_a_strict_threshold() -> None:
    assert Result("test", Path("x"), "x", 80.001, 4).passed
    assert not Result("test", Path("x"), "x", 80.0, 4).passed
    assert Result("test", Path("x"), "x", None, 3).passed
