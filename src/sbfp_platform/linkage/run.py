"""Run row links and write the set Parquet files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sbfp_platform.contracts import LINKAGE_CANDIDATES, LINKAGE_RESULTS
from sbfp_platform.linkage.deterministic import generate_deterministic_candidates
from sbfp_platform.linkage.probabilistic import (
    generate_splink_candidates,
    train_splink_model,
)
from sbfp_platform.linkage.resolve import resolve_candidates
from sbfp_platform.linkage.review_queue import build_review_queue
from sbfp_platform.utils.logging import get_logger

logger = get_logger(__name__)

CHILD_RECORDS_FILE = "silver_child_records.parquet"
CANDIDATES_FILE = "silver_linkage_candidates.parquet"
RESULTS_FILE = "silver_linkage_results.parquet"
REVIEW_FILE = "linkage_review_queue.parquet"
MODEL_FILE = "trained_splink_model.json"


def _load_child_records(config) -> pd.DataFrame:
    source = config.paths.silver_dir / CHILD_RECORDS_FILE
    if not source.is_file():
        raise FileNotFoundError(
            f"Missing silver child records: {source}. Run build-silver before run-linkage."
        )
    records = pd.read_parquet(source)
    required = {
        "child_record_id",
        "school_id",
        "period",
        "lrn_clean",
        "student_name_clean",
        "first_letter_name",
        "birthday_str",
        "sex",
    }
    missing = sorted(required - set(records.columns))
    if missing:
        raise ValueError(f"{source} is missing linkage columns: {', '.join(missing)}")
    invalid_periods = set(records["period"].dropna()) - {"baseline", "endline"}
    if invalid_periods:
        raise ValueError(f"Unexpected period values in {source}: {sorted(invalid_periods)}")
    return records


def output_paths(config) -> dict[str, Path]:
    return {
        "candidates": config.paths.linkage_dir / CANDIDATES_FILE,
        "results": config.paths.linkage_dir / RESULTS_FILE,
        "review": config.paths.linkage_dir / REVIEW_FILE,
        "model": config.paths.linkage_dir / MODEL_FILE,
    }


def run_linkage(config) -> pd.DataFrame:
    """Benchmark exact rules, then train and run the global Splink resolver."""
    records = _load_child_records(config)
    baseline = records.loc[records["period"] == "baseline"].copy()
    endline = records.loc[records["period"] == "endline"].copy()
    deterministic = generate_deterministic_candidates(
        baseline, endline, config.linkage.get("deterministic", {})
    )
    probability_config = config.linkage["probabilistic"]
    paths = output_paths(config)
    model_path = train_splink_model(baseline, endline, probability_config, paths["model"])
    probabilistic = generate_splink_candidates(baseline, endline, probability_config, model_path)
    candidates = pd.concat([deterministic, probabilistic], ignore_index=True)

    results = resolve_candidates(
        probabilistic,
        accept_threshold=float(probability_config["accept_threshold"]),
        review_floor=float(probability_config["review_floor"]),
        ambiguity_margin_weight=float(probability_config["ambiguity_margin_weight"]),
    )
    review = build_review_queue(results)

    LINKAGE_CANDIDATES.validate(candidates, lazy=True)
    LINKAGE_RESULTS.validate(results, lazy=True)
    config.paths.linkage_dir.mkdir(parents=True, exist_ok=True)
    candidates.to_parquet(paths["candidates"], index=False)
    results.to_parquet(paths["results"], index=False)
    review.to_parquet(paths["review"], index=False)

    logger.info(
        "Linkage complete: %d candidate(s), %d accepted, %d queued; wrote %s",
        len(candidates),
        int(results["decision"].eq("accepted").sum()),
        len(review),
        paths["results"],
    )
    return results
