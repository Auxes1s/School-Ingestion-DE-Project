"""The ground-truth answer key must never reach the pipeline.

If it did, every number the platform reports would be circular: the DQA detection rate
and the linkage precision/recall would measure nothing. This is the invariant the whole
design rests on (spec §2.2), so it is enforced structurally rather than by convention.

Rules:
  * No pipeline package may import ``sbfp_platform.evaluation``.
  * No pipeline package may contain a string literal referencing the ground-truth path.
  * ``synthetic`` writes the answer key, so it may reference the path via
    ``config.paths.ground_truth_dir`` (attribute access) but not by literal.
  * dbt models may not select from ground-truth sources.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from sbfp_platform.config import repo_root

#: Packages that make up the pipeline. ``evaluation`` is deliberately absent: it is the
#: only package permitted to read the answer key.
PIPELINE_PACKAGES = (
    "synthetic",
    "ingestion",
    "validation",
    "linkage",
    "transforms",
    "observability",
    "privacy",
    "utils",
)

FORBIDDEN_LITERAL = "ground_truth"
FORBIDDEN_IMPORT = "sbfp_platform.evaluation"


def _pipeline_modules() -> list[Path]:
    src = repo_root() / "src" / "sbfp_platform"
    return sorted(path for package in PIPELINE_PACKAGES for path in (src / package).rglob("*.py"))


@pytest.mark.parametrize("module_path", _pipeline_modules(), ids=lambda p: p.name)
def test_pipeline_module_does_not_import_evaluation(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(FORBIDDEN_IMPORT), (
                    f"{module_path.relative_to(repo_root())} imports {alias.name}. "
                    "Pipeline code must not reach the evaluation layer — that would "
                    "leak ground truth into the pipeline it is meant to measure."
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(FORBIDDEN_IMPORT), (
                f"{module_path.relative_to(repo_root())} imports from {node.module}. "
                "Pipeline code must not reach the evaluation layer."
            )


@pytest.mark.parametrize("module_path", _pipeline_modules(), ids=lambda p: p.name)
def test_pipeline_module_has_no_ground_truth_path_literal(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert FORBIDDEN_LITERAL not in node.value, (
                f"{module_path.relative_to(repo_root())} line {node.lineno} contains the "
                f"literal {node.value!r}. Reach the answer key through "
                "config.paths.ground_truth_dir instead, so the leak test stays meaningful."
            )


def test_dbt_models_do_not_reference_ground_truth() -> None:
    dbt_models = repo_root() / "dbt" / "models"
    if not dbt_models.is_dir():
        pytest.skip("dbt models not yet created")

    offenders = [
        path.relative_to(repo_root())
        for path in dbt_models.rglob("*.sql")
        if FORBIDDEN_LITERAL in path.read_text(encoding="utf-8")
        or "truth_" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"dbt models reference ground truth: {offenders}. Silver and gold models must be "
        "buildable from source data alone."
    )


def test_evaluation_package_is_the_only_reader() -> None:
    """Sanity check that the exclusion list is actually exhaustive."""
    src = repo_root() / "src" / "sbfp_platform"
    packages = {p.name for p in src.iterdir() if p.is_dir() and not p.name.startswith("_")}
    unclassified = packages - set(PIPELINE_PACKAGES) - {"evaluation"}
    assert not unclassified, (
        f"New package(s) {sorted(unclassified)} are not classified as pipeline or "
        "evaluation. Add them to PIPELINE_PACKAGES, or justify the exemption."
    )
