"""Pick links that a person should check."""

from __future__ import annotations

import pandas as pd


def build_review_queue(results: pd.DataFrame) -> pd.DataFrame:
    """List weak or tied links and all school moves for a person to check."""
    if results.empty:
        return results.copy()
    mask = results["decision"].eq("review") | results["review_reason"].eq(
        "school_transfer_detected"
    )
    return (
        results.loc[mask]
        .sort_values(["decision", "match_probability"], ascending=[True, False], kind="stable")
        .reset_index(drop=True)
    )
