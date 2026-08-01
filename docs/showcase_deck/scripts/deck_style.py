"""Shared visual language for the Measured Trust deck."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

ROOT = Path(__file__).resolve().parents[3]
DECK_DIR = ROOT / "docs" / "showcase_deck"
FIGURE_DIR = DECK_DIR / "figures"
TABLE_DIR = DECK_DIR / "tables"

INK = "#0F172A"
SLATE = "#475569"
PAPER = "#FCFAF5"
MIST = "#E7EEF0"
TEAL = "#0F766E"
AMBER = "#D97706"
VIOLET = "#6D28D9"
RED = "#B42318"
GREEN = "#15803D"
BLUE = "#1D4ED8"


def setup() -> None:
    """Configure a legible, presentation-first Matplotlib theme."""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update(
        {
            "figure.facecolor": PAPER,
            "axes.facecolor": PAPER,
            "savefig.facecolor": PAPER,
            "font.family": "DejaVu Sans",
            "text.color": INK,
            "axes.labelcolor": SLATE,
            "axes.edgecolor": MIST,
            "xtick.color": SLATE,
            "ytick.color": SLATE,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
