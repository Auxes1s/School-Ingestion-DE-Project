"""Review-queue selection."""

from __future__ import annotations

import pandas as pd


def build_review_queue(results: pd.DataFrame) -> pd.DataFrame:
    """Return gray/ambiguous decisions plus accepted transfers for confirmation."""
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
