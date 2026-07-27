"""Conservative repository scanner for accidental sensitive-data artifacts."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from sbfp_platform.config import repo_root

# Exclude runs embedded inside hashes or other identifiers. A learner number is a
# standalone 12-digit token, not twelve numeric characters within a hexadecimal key.
LRN_PATTERN = re.compile(r"(?<![0-9A-Za-z.])\d{12}(?![0-9A-Za-z.])")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SENSITIVE_FILENAMES = re.compile(r"(?:learner|student|child).*(?:master|roster)", re.IGNORECASE)
TEXT_SUFFIXES = {".csv", ".json", ".jsonl", ".txt"}
EXCLUDED_PARTS = {".git", ".venv", "tests", "synthetic_raw"}


def scan(root: Path | None = None) -> list[str]:
    """Return human-readable findings; synthetic code and generated folders are excluded."""
    base = (root or repo_root()).resolve()
    try:
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(base),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            check=False,
        )
    except OSError:
        paths = base.rglob("*")
    else:
        paths = (
            (base / name for name in listed.stdout.decode().split("\0") if name)
            if listed.returncode == 0
            else base.rglob("*")
        )
    findings: list[str] = []
    for path in paths:
        relative = path.relative_to(base)
        if (
            not path.is_file()
            or set(relative.parts) & EXCLUDED_PARTS
            or relative.parts[:2] == ("dbt", "target")
        ):
            continue
        if SENSITIVE_FILENAMES.search(path.name):
            findings.append(f"sensitive-looking filename: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if LRN_PATTERN.search(text):
            findings.append(f"12-digit identifier-like value: {relative}")
        if EMAIL_PATTERN.search(text):
            findings.append(f"email address: {relative}")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("Privacy scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Privacy scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
