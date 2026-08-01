"""Check plain text with the Flesch score."""

from __future__ import annotations

import argparse
import ast
import io
import math
import re
import subprocess
import tokenize
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import textstat
from markdown_it import MarkdownIt
from pypdf import PdfReader

MIN_SCORE = 80.0
MIN_WORDS = 4
WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
DOC_SUFFIXES = {".adoc", ".md", ".mdx", ".rst"}
PYTHON_ROOTS = ("src", "dashboards", "orchestration", "tests", "tools")
COMMENT_MARKERS = {
    ".js": "//",
    ".qmd": "#",
    ".r": "#",
    ".rmd": "#",
    ".sh": "#",
    ".sql": "--",
    ".tex": "%",
    ".toml": "#",
    ".typ": "//",
    ".yaml": "#",
    ".yml": "#",
}
NAMED_COMMENT_FILES = {
    ".dockerignore": "#",
    ".env.example": "#",
    ".gitattributes": "#",
    ".gitignore": "#",
    "Dockerfile": "#",
    "Makefile": "#",
}
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
    "dbt_packages",
    "logs",
    "outputs",
    "target",
}
DIRECTIVES = ("!", "fmt:", "noqa", "pragma:", "shellcheck", "type:")


@dataclass(frozen=True)
class Result:
    """Store one score and its source."""

    kind: str
    path: Path
    label: str
    score: float | None
    words: int

    @property
    def passed(self) -> bool:
        """Tell if scored text clears the gate."""
        return self.score is None or self.score > MIN_SCORE


class CoverageError(RuntimeError):
    """Show that a requested scope has no proof."""


def _word_count(text: str) -> int:
    return len(WORD.findall(text))


def _result(kind: str, path: Path, label: str, text: str, *, score_short: bool = False) -> Result:
    words = _word_count(text)
    score = textstat.flesch_reading_ease(text) if words >= MIN_WORDS or score_short else None
    return Result(kind, path, label, score, words)


def _repo_files(root: Path) -> list[Path]:
    try:
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
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
        listed = None
    if listed is not None and listed.returncode == 0:
        return [root / name for name in listed.stdout.decode().split("\0") if name]
    return [path for path in root.rglob("*") if path.is_file()]


def _kept(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return not set(relative.parts) & EXCLUDED_PARTS


def _inline_text(token: object) -> str:
    words: list[str] = []
    for child in getattr(token, "children", None) or []:
        if child.type in {"text", "image"}:
            words.append(child.content)
        elif child.type in {"softbreak", "hardbreak"}:
            words.append(" ")
    return " ".join(words).strip()


def markdown_units(path: Path) -> list[tuple[str, str]]:
    """Read each visible prose block in a Markdown file."""
    parser = MarkdownIt("commonmark").enable("table")
    tokens = parser.parse(path.read_text(encoding="utf-8"))
    units: list[tuple[str, str]] = []
    row: list[str] | None = None
    row_line = 0
    for index, token in enumerate(tokens):
        if token.type == "tr_open":
            row = []
            row_line = index + 1
        elif token.type == "inline" and row is not None:
            text = _inline_text(token)
            if text:
                row.append(text)
                if token.map:
                    row_line = token.map[0] + 1
        elif token.type == "tr_close" and row is not None:
            units.append((f"table row near {row_line}", ". ".join(row)))
            row = None
    headings: list[str] = []
    for index, token in enumerate(tokens):
        if token.type != "inline":
            continue
        parent = tokens[index - 1].type if index else ""
        if parent not in {"heading_open", "paragraph_open"}:
            continue
        text = _inline_text(token)
        if not text:
            continue
        if parent == "heading_open":
            headings.append(text)
            continue
        line = token.map[0] + 1 if token.map else index + 1
        if headings:
            text = ". ".join([*headings, text])
            headings = []
        units.append((f"line {line}", text))
    if headings:
        units.append(("final heading", ". ".join(headings)))
    return units


def markdown_results(root: Path, files: list[Path]) -> list[Result]:
    docs = [path for path in files if path.suffix.lower() in DOC_SUFFIXES and _kept(path, root)]
    if not docs:
        raise CoverageError("Markdown scope found no documentation files.")
    if root / "README.md" not in docs:
        raise CoverageError("Markdown scope did not include README.md.")
    results: list[Result] = []
    for path in sorted(docs):
        for label, text in markdown_units(path):
            results.append(_result("markdown", path, label, text))
    if not any(result.score is not None for result in results):
        raise CoverageError("Markdown scope found no prose blocks that can be scored.")
    return results


def _docstrings(tree: ast.AST) -> Iterable[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            text = ast.get_docstring(node, clean=True)
            if text:
                yield getattr(node, "lineno", 1), text


def _python_comment_groups(source: str) -> Iterable[tuple[int, str]]:
    current_line = 0
    current_text: list[str] = []
    current_start = 0
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        text = token.string.lstrip("#").strip()
        if not text or text.lower().startswith(DIRECTIVES):
            continue
        full_line = not source.splitlines()[token.start[0] - 1][: token.start[1]].strip()
        if full_line and current_text and token.start[0] == current_line + 1:
            current_text.append(text)
        else:
            if current_text:
                yield current_start, " ".join(current_text)
            current_start = token.start[0]
            current_text = [text]
        current_line = token.end[0]
        if not full_line:
            yield current_start, " ".join(current_text)
            current_text = []
    if current_text:
        yield current_start, " ".join(current_text)


def _plain_comment_groups(path: Path, marker: str) -> Iterable[tuple[int, str]]:
    current_start = 0
    current_line = 0
    current_text: list[str] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.lstrip()
        if marker not in raw or (marker == "%" and not stripped.startswith(marker)):
            if current_text:
                yield current_start, " ".join(current_text)
                current_text = []
            continue
        offset = raw.find(marker)
        if offset > 0 and not raw[offset - 1].isspace():
            continue
        text = raw[offset + len(marker) :].strip()
        if not text or text.lower().startswith(DIRECTIVES):
            continue
        full_line = not raw[:offset].strip()
        if full_line and current_text and number == current_line + 1:
            current_text.append(text)
        else:
            if current_text:
                yield current_start, " ".join(current_text)
            current_start = number
            current_text = [text]
        current_line = number
        if not full_line:
            yield current_start, " ".join(current_text)
            current_text = []
    if current_text:
        yield current_start, " ".join(current_text)


def comment_results(root: Path, files: list[Path] | None = None) -> list[Result]:
    files = files or _repo_files(root)
    results: list[Result] = []
    for path in sorted(files):
        if not path.is_file() or not _kept(path, root):
            continue
        relative = path.relative_to(root)
        if path.suffix == ".py" and relative.parts[0] in PYTHON_ROOTS:
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError as error:
                raise CoverageError(
                    f"Could not parse Python comments in {relative}: {error}"
                ) from error
            for line, text in _docstrings(tree):
                results.append(_result("docstring", path, f"line {line}", text))
            for line, text in _python_comment_groups(source):
                results.append(_result("comment", path, f"line {line}", text))
            continue
        marker = NAMED_COMMENT_FILES.get(path.name) or COMMENT_MARKERS.get(path.suffix.lower())
        if marker:
            for line, text in _plain_comment_groups(path, marker):
                results.append(_result("comment", path, f"line {line}", text))
    if not any(result.score is not None for result in results):
        raise CoverageError("Comment scope found no prose blocks that can be scored.")
    return results


def _clean_page(lines: list[str], repeated: set[str]) -> str:
    kept: list[str] = []
    for raw in lines:
        line = " ".join(raw.split())
        if not line or line in repeated or re.fullmatch(r"\d+", line):
            continue
        if any(mark in line for mark in ("://", "=", "{", "}", "\\", "|>")):
            continue
        if (
            _word_count(line)
            and sum(char.isalpha() or char.isspace() for char in line) / len(line) > 0.7
        ):
            kept.append(line)
    return " ".join(kept)


def slide_results(root: Path, files: list[Path]) -> list[Result]:
    deck_root = root / "docs" / "showcase_deck"
    sources = [path for path in files if path.parent == deck_root and path.suffix == ".tex"]
    pdfs = [path for path in files if path.parent == deck_root and path.suffix == ".pdf"]
    if not sources:
        raise CoverageError("Slide scope requires a Beamer source in docs/showcase_deck.")
    if not pdfs:
        raise CoverageError("Slide scope requires a compiled PDF in docs/showcase_deck.")
    results: list[Result] = []
    for path in sorted(pdfs):
        pages = [(page.extract_text() or "").splitlines() for page in PdfReader(path).pages]
        counts = Counter(line.strip() for page in pages for line in set(page) if line.strip())
        repeated = {
            line for line, count in counts.items() if count >= max(2, math.ceil(len(pages) / 2))
        }
        for number, page in enumerate(pages, start=1):
            text = _clean_page(page, repeated)
            results.append(_result("slide", path, f"page {number}", text, score_short=True))
    if not results or any(result.words == 0 for result in results):
        raise CoverageError("Slide scope could not read visible text from every PDF page.")
    return results


def audit(root: Path, scopes: set[str]) -> list[Result]:
    files = _repo_files(root)
    results: list[Result] = []
    if "markdown" in scopes:
        results.extend(markdown_results(root, files))
    if "comments" in scopes:
        results.extend(comment_results(root, files))
    if "slides" in scopes:
        results.extend(slide_results(root, files))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--scope",
        action="append",
        choices=("markdown", "comments", "slides"),
        help="Limit the audit. Repeat for more than one scope.",
    )
    parser.add_argument("--all", action="store_true", help="Print passing and skipped text too.")
    args = parser.parse_args()
    root = args.root.resolve()
    scopes = set(args.scope or ("markdown", "comments", "slides"))
    try:
        results = audit(root, scopes)
    except CoverageError as error:
        print(f"COVERAGE FAIL: {error}")
        return 1
    failed = [result for result in results if not result.passed]
    shown = results if args.all else failed
    for result in shown:
        relative = result.path.relative_to(root)
        if result.score is None:
            print(f"SKIP {'-':>7s} {result.words:5d} {result.kind:9s} {relative}:{result.label}")
        else:
            mark = "PASS" if result.passed else "FAIL"
            print(
                f"{mark} {result.score:7.3f} {result.words:5d} "
                f"{result.kind:9s} {relative}:{result.label}"
            )
    scored = [result for result in results if result.score is not None]
    skipped = len(results) - len(scored)
    print(
        f"\n{len(scored) - len(failed)}/{len(scored)} scored units are above {MIN_SCORE:.0f}; {skipped} short units reported but not scored."
    )
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
