"""Render the reusable trust-gate architecture."""

from __future__ import annotations

import matplotlib.pyplot as plt
from deck_style import AMBER, BLUE, FIGURE_DIR, GREEN, INK, MIST, SLATE, TEAL, VIOLET, setup
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def main() -> None:
    setup()
    fig, ax = plt.subplots(figsize=(13.333, 6.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    stages = [
        ("PRESERVE", "Raw\nevidence", "files + provenance", AMBER),
        ("STANDARDIZE", "Comparable\nfields", "schema + types", BLUE),
        ("CHALLENGE", "Quality\nevidence", "21 rules", TEAL),
        ("RECONCILE", "Linked\nentities", "rules + Splink", VIOLET),
        ("SERVE", "Decision\nproducts", "marts + exports", GREEN),
    ]
    xs = [0.035, 0.23, 0.425, 0.62, 0.815]
    width = 0.15
    for index, ((verb, output, proof, color), x) in enumerate(zip(stages, xs, strict=True)):
        box = FancyBboxPatch(
            (x, 0.28),
            width,
            0.46,
            boxstyle="round,pad=0.014,rounding_size=0.025",
            linewidth=1.8,
            edgecolor=color,
            facecolor="#FFFFFF",
        )
        ax.add_patch(box)
        ax.text(x + 0.018, 0.66, verb, fontsize=11.5, weight="bold", color=color)
        ax.text(x + 0.018, 0.55, output, fontsize=13.5, weight="bold", color=INK, va="center")
        ax.text(x + 0.018, 0.37, proof, fontsize=11.5, color=SLATE)
        ax.text(x + width - 0.018, 0.69, f"0{index + 1}", fontsize=10.5, color=MIST, ha="right")
        if index < len(stages) - 1:
            ax.add_patch(
                FancyArrowPatch(
                    (x + width + 0.004, 0.44),
                    (xs[index + 1] - 0.004, 0.44),
                    arrowstyle="-|>",
                    mutation_scale=14,
                    linewidth=1.6,
                    color=SLATE,
                )
            )

    ax.text(
        0.035,
        0.15,
        "Reusable pattern: customer · patient · beneficiary · workforce · survey · education",
        fontsize=14,
        color=SLATE,
    )

    out = FIGURE_DIR / "trust_pipeline.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
