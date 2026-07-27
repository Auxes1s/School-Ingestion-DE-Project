"""Small, dependency-free HTML reports generated from privacy-safe scorecards."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd

STYLE = """
body{font-family:system-ui,sans-serif;max-width:1100px;margin:40px auto;color:#17202a}
h1{color:#155b52} .cards{display:flex;gap:16px;flex-wrap:wrap}.card{padding:14px 18px;
border:1px solid #d8e3e1;border-radius:10px;background:#f7fbfa}.value{font-size:1.7rem;
font-weight:700}table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{padding:7px;
border-bottom:1px solid #ddd;text-align:left}th{background:#edf6f4}.note{color:#536b68}
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' "
        f"content='width=device-width'><title>{escape(title)}</title><style>{STYLE}</style>"
        f"</head><body><h1>{escape(title)}</h1>{body}<p class='note'>Synthetic data only. "
        "No real learner records.</p></body></html>"
    )


def _card(label: str, value: str) -> str:
    return f"<div class='card'><div>{escape(label)}</div><div class='value'>{escape(value)}</div></div>"


def write_reports(
    config: Any,
    dqa: pd.DataFrame,
    linkage: pd.DataFrame,
    child_records: pd.DataFrame,
) -> tuple[Path, ...]:
    """Write DQA, pipeline, and evaluation-readiness summaries."""
    directory = config.paths.reports_dir
    directory.mkdir(parents=True, exist_ok=True)

    injected = int(dqa["injected_count"].sum())
    detected = int(dqa["detected_count"].sum())
    dqa_body = (
        "<div class='cards'>"
        + "".join(
            [
                _card("Rules executed", str(len(dqa))),
                _card("Injected defects", f"{injected:,}"),
                _card("Detected", f"{detected:,}"),
                _card("Weighted detection", f"{detected / injected:.1%}" if injected else "n/a"),
            ]
        )
        + "</div>"
        + dqa.to_html(index=False, float_format=lambda value: f"{value:.3f}")
    )

    operating = linkage[(linkage["method"] == "combined") & (linkage["threshold"] == 0.75)].iloc[0]
    pipeline_body = (
        "<div class='cards'>"
        + "".join(
            [
                _card("Profile", str(config.profile)),
                _card("Source child rows", f"{len(child_records):,}"),
                _card(
                    "Accepted links",
                    f"{int(operating['true_positives'] + operating['false_positives']):,}",
                ),
                _card("Linkage F1", f"{operating['f1']:.1%}"),
            ]
        )
        + "</div><h2>Threshold sweep</h2>"
        + linkage.to_html(index=False, float_format=lambda value: f"{value:.3f}")
    )

    panel_path = config.paths.gold_dir / "gold_evaluation_child_panel.parquet"
    panel = pd.read_parquet(panel_path) if panel_path.is_file() else pd.DataFrame()
    if panel.empty:
        readiness_body = "<p>The evaluation panel has not been materialized.</p>"
    else:
        required = [
            "height_cm_baseline",
            "height_cm_endline",
            "weight_kg_baseline",
            "weight_kg_endline",
        ]
        complete = panel[required].notna().all(axis=1).mean()
        readiness_body = (
            "<div class='cards'>"
            + "".join(
                [
                    _card("Linked panel rows", f"{len(panel):,}"),
                    _card("Complete anthropometry", f"{complete:.1%}"),
                    _card("Critical issue rows", f"{int(panel['has_critical_issue'].sum()):,}"),
                    _card("Identity fields exported", "0"),
                ]
            )
            + "</div>"
        )

    reports = (
        ("data_quality_report.html", "Data Quality Report", dqa_body),
        ("pipeline_run_summary.html", "Pipeline Run Summary", pipeline_body),
        ("evaluation_readiness_report.html", "Evaluation Readiness Report", readiness_body),
    )
    written: list[Path] = []
    for filename, title, body in reports:
        path = directory / filename
        path.write_text(_page(title, body), encoding="utf-8")
        written.append(path)
    return tuple(written)
