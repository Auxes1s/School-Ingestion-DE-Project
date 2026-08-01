"""Train, persist, load, and score the tiny-profile Splink model."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from sbfp_platform.config import load_config
from sbfp_platform.linkage.probabilistic import (
    generate_splink_candidates,
    train_splink_model,
)
from sbfp_platform.linkage.resolve import resolve_candidates

THRESHOLD = 0.10

config = load_config(profile="tiny")
records = pd.read_parquet(config.paths.silver_dir / "silver_child_records.parquet")
baseline = records.loc[records["period"].eq("baseline")]
endline = records.loc[records["period"].eq("endline")]
settings = config.linkage["probabilistic"]

with TemporaryDirectory() as temporary_directory:
    model_path = Path(temporary_directory) / "trained_splink_model.json"
    train_splink_model(baseline, endline, settings, model_path)
    pairs = generate_splink_candidates(baseline, endline, settings, model_path)
    links = resolve_candidates(
        pairs,
        accept_threshold=THRESHOLD,
        review_floor=THRESHOLD,
        ambiguity_margin_weight=float(settings["ambiguity_margin_weight"]),
    )

scorecard = pd.read_parquet(config.paths.gold_dir / "gold_linkage_scorecard.parquet").set_index(
    ["method", "threshold"]
)
result = scorecard.loc[("splink", THRESHOLD)]

print(f"Accepted links: {links['decision'].eq('accepted').sum()}")
print(f"Precision:      {result['precision']:.2%}")
print(f"Recall:         {result['recall']:.2%}")
print(f"True links:     {int(result['true_positives'])}")
print(f"False links:    {int(result['false_positives'])}")
