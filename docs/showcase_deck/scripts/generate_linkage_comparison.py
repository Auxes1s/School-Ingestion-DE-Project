"""Compare measured entity-resolution performance at the approved threshold."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from deck_style import FIGURE_DIR, GREEN, INK, MIST, ROOT, SLATE, VIOLET, setup


def main() -> None:
    setup()
    scorecard = pd.read_parquet(ROOT / "data/lakehouse/gold/gold_linkage_scorecard.parquet")
    selected = scorecard[scorecard["threshold"].sub(0.10).abs() < 1e-9].set_index("method")
    order = ["deterministic", "splink"]
    labels = ["Exact-rule benchmark", "Trained Splink"]
    colors = [SLATE, VIOLET]
    recall = [float(selected.loc[m, "recall"]) * 100 for m in order]
    precision = [float(selected.loc[m, "precision"]) * 100 for m in order]

    fig, ax = plt.subplots(figsize=(13.333, 5.0))
    y = [1, 0]
    ax.barh(y, recall, color=colors, height=0.56)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.62, 1.62)
    ax.set_yticks(y, labels, fontsize=17, weight="bold")
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"], fontsize=13)
    ax.grid(axis="x", color=MIST, linewidth=1)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="y", length=0, pad=12)
    ax.tick_params(axis="x", length=0)
    for yi, value, p in zip(y, recall, precision, strict=True):
        ax.text(
            value - 2,
            yi,
            f"{value:.1f}% recall",
            ha="right",
            va="center",
            color="white",
            fontsize=16,
            weight="bold",
        )
        ax.text(value + 1.8, yi, f"{p:.1f}% precision", va="center", color=INK, fontsize=14)

    lift = recall[-1] - recall[0]
    ax.annotate(
        f"+{lift:.1f} pp recall",
        xy=(recall[-1], 0),
        xytext=(recall[0] + 7, 0.54),
        arrowprops={"arrowstyle": "->", "color": GREEN, "lw": 2},
        color=GREEN,
        fontsize=16,
        weight="bold",
    )
    fig.text(
        0.02,
        0.01,
        "Fixed synthetic benchmark · benchmark-selected threshold · trained Splink: 812 true links, 0 false accepted links",
        fontsize=13,
        color=SLATE,
    )

    out = FIGURE_DIR / "linkage_comparison.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
