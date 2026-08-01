"""Render one fictional identity as it appears in disconnected systems."""

from __future__ import annotations

import matplotlib.pyplot as plt
from deck_style import AMBER, FIGURE_DIR, INK, MIST, RED, SLATE, TEAL, setup
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def card(ax, x, label, lines, accent):
    box = FancyBboxPatch(
        (x, 0.22),
        0.25,
        0.58,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        linewidth=1.6,
        edgecolor=accent,
        facecolor="#FFFFFF",
    )
    ax.add_patch(box)
    ax.text(x + 0.025, 0.73, label.upper(), fontsize=13, weight="bold", color=accent)
    for row, (field, value, changed) in enumerate(lines):
        y = 0.61 - row * 0.115
        ax.text(x + 0.025, y, field, fontsize=10.5, color=SLATE)
        ax.text(
            x + 0.025,
            y - 0.05,
            value,
            fontsize=13,
            weight="bold" if changed else "normal",
            color=RED if changed else INK,
        )


def main() -> None:
    setup()
    fig, ax = plt.subplots(figsize=(13.333, 7.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    card(
        ax,
        0.05,
        "System A",
        [
            ("Name", "SAMIRA N. REYES", False),
            ("Birth date", "2014-08-11", False),
            ("Sex", "F", False),
        ],
        TEAL,
    )
    card(
        ax,
        0.375,
        "System B",
        [
            ("Name", "REYES, SAMRA N", True),
            ("Birth date", "08/11/2014", True),
            ("Sex", "Female", False),
        ],
        AMBER,
    )
    card(
        ax,
        0.70,
        "System C",
        [
            ("Name", "Samira Nur Reyes", True),
            ("Birth date", "11-08-2014", True),
            ("Sex", "M", True),
        ],
        RED,
    )

    for x1, x2 in ((0.305, 0.37), (0.63, 0.695)):
        ax.add_patch(
            FancyArrowPatch(
                (x1, 0.51),
                (x2, 0.51),
                arrowstyle="-|>",
                mutation_scale=16,
                linewidth=1.8,
                color=MIST,
            )
        )

    ax.text(
        0.50,
        0.11,
        "Exact equality sees three records.  A measured process asks whether they are one.",
        fontsize=17.5,
        weight="bold",
        color=INK,
        ha="center",
    )

    out = FIGURE_DIR / "identity_variation.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
