"""Generate the deck-style linkage chart for the square publication card."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from deck_style import ROOT, SLATE, VIOLET, setup


def main() -> None:
    setup()
    scorecard = pd.read_parquet(ROOT / "data/lakehouse/gold/gold_linkage_scorecard.parquet")
    selected = scorecard[scorecard["threshold"].sub(0.10).abs() < 1e-9].set_index("method")

    labels = ["Exact-rule benchmark", "Trained Splink"]
    methods = ["deterministic", "splink"]
    values = [float(selected.loc[method, "recall"]) * 100 for method in methods]
    colors = [SLATE, VIOLET]

    fig, ax = plt.subplots(figsize=(7.2, 2.55))
    y = [1, 0]
    ax.barh(y, values, color=colors, height=0.58)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.48, 1.48)
    ax.set_yticks(y, labels, fontsize=14, weight="bold")
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0, pad=18)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for yi, value in zip(y, values, strict=True):
        ax.text(
            value - 1.8,
            yi,
            f"{value:.1f}% recall",
            color="white",
            fontsize=13,
            weight="bold",
            va="center",
            ha="right",
        )
    output = ROOT / "docs/showcase_deck/publication_materials/linkage_lift_publication.pdf"
    fig.savefig(output, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()
