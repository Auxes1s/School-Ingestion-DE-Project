"""Entry point for ``sbfp-platform run-dqa``.

Reads the lakehouse, runs every rule declared in ``configs/dqa_rules.yml``, and writes
the row-level issue registry that the DQA scorecard is computed from (spec §3.1).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sbfp_platform.utils.logging import get_logger, new_run_id
from sbfp_platform.validation.engine import RuleOutcome, evaluate
from sbfp_platform.validation.frames import load_frames

logger = get_logger(__name__)

ISSUE_TABLE = "silver_dqa_issues"


def issues_path(config) -> Path:
    return config.paths.silver_dir / f"{ISSUE_TABLE}.parquet"


def write_issues(issues: pd.DataFrame, config) -> Path:
    """Materialize the issue registry, replacing any registry from a previous run."""
    destination = issues_path(config)
    destination.parent.mkdir(parents=True, exist_ok=True)
    issues.to_parquet(destination, index=False)
    return destination


def _report(issues: pd.DataFrame, outcomes: list[RuleOutcome], destination: Path) -> None:
    ran = [outcome for outcome in outcomes if outcome.ran]
    skipped = [outcome for outcome in outcomes if not outcome.ran]

    logger.info(
        "DQA complete: %d issue(s) from %d rule(s); %d rule(s) skipped.",
        len(issues),
        len(ran),
        len(skipped),
    )
    if not issues.empty:
        by_severity = issues["severity"].value_counts().to_dict()
        logger.info(
            "By severity: %s",
            ", ".join(f"{severity}={count}" for severity, count in sorted(by_severity.items())),
        )
        firing = [outcome for outcome in ran if outcome.issue_count]
        for outcome in sorted(firing, key=lambda o: o.issue_count, reverse=True):
            logger.info("  %s: %d", outcome.rule_id, outcome.issue_count)
    for outcome in skipped:
        logger.warning("  %s skipped (%s)", outcome.rule_id, outcome.skipped_reason)
    logger.info("Issue registry written to %s", destination)


def run_dqa(config) -> pd.DataFrame:
    """Run the DQA rule engine over the lakehouse and write the issue registry.

    Raises:
        MissingSilverError: if the silver tables the rules need have not been built.
        RuleRegistryError: if a configured rule has no implementation, or the reverse.
    """
    run_id = new_run_id("dqa")
    frames = load_frames(config)
    logger.info(
        "Loaded %s for run %s",
        ", ".join(f"{name}={len(frame):,} rows" for name, frame in sorted(frames.items())),
        run_id,
    )

    issues, outcomes = evaluate(frames, config, run_id=run_id)
    destination = write_issues(issues, config)
    _report(issues, outcomes, destination)
    return issues
