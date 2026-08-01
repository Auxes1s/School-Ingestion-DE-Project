"""Load settings and find paths.

This is a fixed rule from spec §9. Each slice must read its settings here. No later step
may read ``configs/*.yml`` on its own or copy a path from ``configs/paths.yml``.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILES = (
    "project",
    "paths",
    "synthetic_data",
    "dqa_rules",
    "linkage_rules",
    "schema_registry",
)

VALID_PROFILES = ("tiny", "demo", "large")


def repo_root() -> Path:
    """Find the repo root.

    Try ``SBFP_REPO_ROOT`` first. If it is not set, walk up from this file until a
    ``configs`` folder is found. Tests and Dagster can set the key to use a test tree.
    """
    env = os.environ.get("SBFP_REPO_ROOT")
    if env:
        return Path(env).resolve()

    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "configs" / "project.yml").is_file():
            return candidate
    raise RuntimeError(
        "Could not locate repository root: no ancestor contains configs/project.yml. "
        "Set SBFP_REPO_ROOT to override."
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required config file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@dataclass(frozen=True)
class Paths:
    """Full, set file tree paths for one run."""

    root: Path
    raw_data_dir: Path
    ground_truth_dir: Path
    lakehouse_dir: Path
    bronze_dir: Path
    silver_dir: Path
    gold_dir: Path
    linkage_dir: Path
    duckdb_path: Path
    outputs_dir: Path
    exports_dir: Path
    reports_dir: Path
    raw_subdirs: dict[str, Path]

    def ensure(self) -> None:
        """Create every managed folder. Use this rule as shown. Use this rule as shown."""
        for directory in (
            self.raw_data_dir,
            self.ground_truth_dir,
            self.bronze_dir,
            self.silver_dir,
            self.gold_dir,
            self.linkage_dir,
            self.exports_dir,
            self.reports_dir,
            *self.raw_subdirs.values(),
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Config:
    """Fully set settings for one pipeline run. Use this rule as shown."""

    profile: str
    seed: int
    paths: Paths
    project: dict[str, Any]
    synthetic: dict[str, Any]
    dqa: dict[str, Any]
    linkage: dict[str, Any]
    schema_registry: dict[str, Any]

    @property
    def scale(self) -> dict[str, int]:
        """Entity counts for the active profile. Use this rule as shown."""
        return self.synthetic["profiles"][self.profile]

    @property
    def issue_rates(self) -> dict[str, float]:
        return self.synthetic["issue_rates"]

    @property
    def detectable(self) -> dict[str, bool]:
        """Which injected defect types a DQA rule is expected to catch (spec §2.1). Use this rule as shown."""
        return self.synthetic["detectable"]

    @property
    def dqa_rules(self) -> list[dict[str, Any]]:
        return self.dqa["rules"]

    @property
    def dqa_thresholds(self) -> dict[str, Any]:
        return self.dqa["thresholds"]

    def rule_for_defect(self, defect_type: str) -> str | None:
        """Map an injected defect type to the rule expected to catch it.

        This is the join key for the DQA scorecard (spec §3.1).
        """
        for rule in self.dqa_rules:
            if defect_type in (rule.get("detects") or []):
                return rule["rule_id"]
        return None


@functools.lru_cache(maxsize=8)
def _load_raw(root_str: str) -> dict[str, dict[str, Any]]:
    root = Path(root_str)
    return {name: _load_yaml(root / "configs" / f"{name}.yml") for name in CONFIG_FILES}


def load_config(profile: str | None = None, seed: int | None = None) -> Config:
    """Load settings for a run."""
    root = repo_root()
    raw = _load_raw(str(root))

    project = raw["project"]
    resolved_profile = profile or project["default_profile"]
    if resolved_profile not in VALID_PROFILES:
        raise ValueError(f"Unknown profile {resolved_profile!r}. Expected one of {VALID_PROFILES}.")
    if resolved_profile not in raw["synthetic_data"]["profiles"]:
        raise ValueError(
            f"Profile {resolved_profile!r} is not defined in configs/synthetic_data.yml."
        )

    p = raw["paths"]
    paths = Paths(
        root=root,
        raw_data_dir=root / p["raw_data_dir"],
        ground_truth_dir=root / p["ground_truth_dir"],
        lakehouse_dir=root / p["lakehouse_dir"],
        bronze_dir=root / p["bronze_dir"],
        silver_dir=root / p["silver_dir"],
        gold_dir=root / p["gold_dir"],
        linkage_dir=root / p["linkage_dir"],
        duckdb_path=root / p["duckdb_path"],
        outputs_dir=root / p["outputs_dir"],
        exports_dir=root / p["exports_dir"],
        reports_dir=root / p["reports_dir"],
        raw_subdirs={k: root / v for k, v in p["raw_subdirs"].items()},
    )

    return Config(
        profile=resolved_profile,
        seed=seed if seed is not None else project["default_seed"],
        paths=paths,
        project=project,
        synthetic=raw["synthetic_data"],
        dqa=raw["dqa_rules"],
        linkage=raw["linkage_rules"],
        schema_registry=raw["schema_registry"],
    )
