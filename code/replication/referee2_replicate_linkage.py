"""Run the independent SQL linkage replication and compare it with gold."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = ROOT / "code" / "replication" / "referee2_replicate_linkage.sql"
SCORECARD_PATH = ROOT / "data" / "lakehouse" / "gold" / "gold_linkage_scorecard.parquet"
METRICS = (
    "true_positives",
    "false_positives",
    "false_negatives",
    "precision",
    "recall",
    "f1",
    "transfer_recall",
)


def main() -> None:
    """Require exact agreement between independent SQL and pipeline scorecards."""
    connection = duckdb.connect()
    connection.execute(f"SET file_search_path = '{ROOT.as_posix()}'")
    replicated = connection.execute(SQL_PATH.read_text(encoding="utf-8")).fetch_df()
    expected = pd.read_parquet(SCORECARD_PATH)
    expected = expected.loc[expected["threshold"].eq(0.10), ["method", *METRICS]]

    comparison = replicated.merge(expected, on="method", suffixes=("_sql", "_pipeline"))
    if set(comparison["method"]) != {"deterministic", "splink"}:
        raise AssertionError("Replication did not produce both linkage methods")
    for metric in METRICS:
        pd.testing.assert_series_equal(
            comparison[f"{metric}_sql"],
            comparison[f"{metric}_pipeline"],
            check_names=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )
    print(replicated.to_string(index=False))
    print("Independent SQL replication matches the pipeline scorecard.")


if __name__ == "__main__":
    main()
