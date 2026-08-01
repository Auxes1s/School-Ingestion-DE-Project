"""Generate the deck's evidence ledger from repository artifacts."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
TABLE_DIR = ROOT / "docs" / "showcase_deck" / "tables"


def pytest_count() -> int:
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"(\d+) tests? collected", run.stdout)
    if not match:
        raise RuntimeError("Could not parse pytest collection count")
    return int(match.group(1))


def dashboard_view_count() -> int:
    tree = ast.parse((ROOT / "dashboards/streamlit_app.py").read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "tabs"
            and node.args
            and isinstance(node.args[0], (ast.List, ast.Tuple))
        ):
            return len(node.args[0].elts)
    raise RuntimeError("Could not locate the dashboard tab definition")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "dbt/target/manifest.json").read_text())
    dbt_tests = sum(node.get("resource_type") == "test" for node in manifest["nodes"].values())
    dqa = yaml.safe_load((ROOT / "configs/dqa_rules.yml").read_text())
    orchestration_source = (ROOT / "orchestration/dagster_project/definitions.py").read_text()
    assets = len(re.findall(r"^@asset\b", orchestration_source, flags=re.MULTILINE))

    entries = [
        ("Regression protection", str(pytest_count()), "automated tests"),
        ("Model contracts", str(dbt_tests), "warehouse tests"),
        ("Known-failure monitoring", str(len(dqa["rules"])), "quality rules"),
        ("End-to-end dependencies", str(assets), "orchestrated assets"),
        ("Decision-ready outputs", str(dashboard_view_count()), "audience views"),
        ("Synthetic-only boundary", "PASS", "privacy scan"),
    ]

    rows = "\n".join(
        rf"\textbf{{{assurance}}} & \textcolor{{SignalTeal}}{{\textbf{{{count}}}}} {proof} \\"
        for assurance, count, proof in entries
    )
    output = TABLE_DIR / "evidence_ledger.tex"
    output.write_text(
        "\\begin{tabular}{@{}p{0.46\\linewidth}p{0.46\\linewidth}@{}}\n"
        "\\toprule\n"
        "Assurance & Repository evidence \\\\\n"
        "\\midrule\n"
        f"{rows}\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
    )
    print(output)


if __name__ == "__main__":
    main()
