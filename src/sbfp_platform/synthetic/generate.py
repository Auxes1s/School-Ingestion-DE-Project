"""Synthetic source-file generator and answer-key writer (spec §2, §5, §7).

``generate_all`` writes two trees. ``config.paths.raw_data_dir`` gets messy Excel and
CSV files of the kind a school actually submits: inconsistent headers drawn from the
alias pool, varying sheet names, dates in five different encodings, blanks, duplicated
rows. The answer-key directory — reached only through the config object's path
attribute, never by literal — gets three parquet tables recording exactly what the true
world was and exactly which cells were corrupted.

Everything hinges on the two sides agreeing about record identity, because the answer
key is joined to the pipeline's output on ``record_id`` and nothing else.

**record_id derivation — the recipe slice 3 must reproduce, verbatim.**

1. ``rel_path`` is the file's path relative to ``config.paths.raw_data_dir``, rendered
   with forward slashes: ``Path.relative_to(raw_data_dir).as_posix()``. Example:
   ``"baseline/baseline_100003_20241004.xlsx"``.
2. ``source_file_id = stable_id(rel_path)`` — 16 hex characters, no prefix.
3. ``source_row_number`` is the 1-based position of the data row within its sheet or
   CSV, counting data rows only. The header line is not counted, so the first data row
   is ``1`` (``df.index + 1`` after a default ``read_excel`` / ``read_csv``).
4. ``record_id = stable_id(source_file_id, source_row_number)`` — 16 hex characters, no
   prefix. The first argument is the *digest* from step 2, not the path.

``stable_id`` is :func:`sbfp_platform.utils.hashing.stable_id`: parts joined with
``"|"``, first 16 characters of the SHA-256 hex digest. Row order — including injected
duplicate rows — is finalized before any identifier is assigned, because inserting a
row shifts every identifier below it.

Defects with no row of their own are recorded against the identifier of the thing they
belong to:

* file-scoped (``school_name_drift``, ``late_submission``) → ``record_id`` is the
  ``source_file_id``. A file-scoped DQA rule must emit its issue with that value.
* ``digit_heaping`` is a school-period property but is recorded per affected row, so
  that the configured rate stays a per-record rate and the join stays row-level. Every
  height in an affected school-period is heaped, so a rule that flags every row of a
  heaping school-period scores perfect precision.

**Determinism.** One seed. Named substreams are derived from it by
``default_rng([seed, tag(name)])``, so adding a draw in one part of the generator does
not shift the numbers in another. No global random state and no wall-clock value ever
enters file content or a filename; XLSX archives are rewritten with a fixed epoch (see
``writers.py``). Same seed and profile give byte-identical raw files.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sbfp_platform.contracts import TRUTH_CHILDREN, TRUTH_DEFECTS, TRUTH_LINKS
from sbfp_platform.synthetic import names, world
from sbfp_platform.synthetic.identity import record_id as make_record_id
from sbfp_platform.synthetic.identity import source_file_id as make_file_id
from sbfp_platform.synthetic.writers import write_table
from sbfp_platform.utils.hashing import stable_id
from sbfp_platform.utils.logging import get_logger

LOGGER = get_logger(__name__)

#: Excel's day zero. Serial 1 is 1900-01-01, and the 1900 leap-year bug means the
#: epoch used for arithmetic is two days before that.
EXCEL_EPOCH = dt.date(1899, 12, 30)

#: Digit heaping rounds heights to this step. See world.MIN_HEIGHT_GAIN_CM.
_HEAPING_STEP_CM = 5.0

#: Impossible date strings. Each is either an invalid calendar date or lands outside
#: the configured plausible birth-year window.
_IMPOSSIBLE_DATES = (
    "2015-02-30",
    "31/06/2016",
    "2014-13-05",
    "0000-00-00",
    "1899-01-01",
    "2099-07-04",
    "not recorded",
)

_SEX_STYLES = (
    ("M", "F"),
    ("Male", "Female"),
    ("MALE", "FEMALE"),
    ("Lalaki", "Babae"),
    ("1", "2"),
    ("Boy", "Girl"),
)

#: Headers the registry does not know. They must survive as schema drift rather than be
#: dropped (spec §4), and no DQA rule targets them, so they cost the scorecard nothing.
_UNMAPPED_HEADERS = ("No.", "Remarks", "Adviser", "Status", "Section")

_SUBMISSION_FIELDS = (
    "school_name",
    "school_id",
    "lrn",
    "student_name",
    "birth_date",
    "sex",
    "grade",
    "height_cm",
    "weight_kg",
    "measurement_date",
)

#: Optional columns a file may simply not have. Neither has a DQA rule attached, so an
#: absent one shows up as schema drift and nothing else.
_DROPPABLE_FIELDS = ("school_id", "grade")

_RAW_README = """# Synthetic raw submissions

**Every file in this tree is synthetic.** It was produced by
`sbfp-platform generate-demo-data` from a fixed seed. No row, name, learner reference
number, school, or measurement here corresponds to a real person, a real school, or a
real record. The platform this repository builds is modeled on a real school-feeding
evaluation pipeline, but shares no data with it.

The files are deliberately messy, in the ways real submissions are messy: column
headers spelled differently from school to school, sheet names that vary, dates encoded
as Excel serials or ambiguous `DD/MM` strings, blank cells, duplicated rows, and school
names that do not exactly match the masterlist. Recovering clean data from this tree is
the problem the pipeline exists to solve.

Layout:

| Directory | Contents |
|---|---|
| `baseline/` | one submission per school, first measurement wave |
| `endline/` | one submission per school, second measurement wave |
| `enrollment/` | enrollment snapshot, one row per school |
| `allocation/` | program allocation, one row per school |
| `reference/` | school masterlist |

Regenerate with `make generate`. Same seed and profile give byte-identical files.
"""

_TRUTH_README = """# Answer key

**Synthetic throughout.** These tables describe the world the generator invented and
the exact corruptions it applied to it. Nothing here refers to a real person or a real
school.

| File | One row per | Used for |
|---|---|---|
| `truth_children.parquet` | true child, pre-corruption | population reference |
| `truth_links.parquet` | link that should be found | the recall denominator |
| `truth_defects.parquet` | injected defect | the DQA detection rate |

Two rules govern this directory:

1. **Only the evaluation layer reads it.** A pytest AST-scans every pipeline package
   and fails if one imports the evaluation package or names this path. If the pipeline
   could see the answers, every number it reports would be circular.
2. **`truth_links` contains only non-attrited children.** Children who genuinely left
   the program are true non-matches. Counting them in the denominator is the easiest
   way to produce a linkage recall figure that is both flattering and wrong.

`truth_defects.record_id` joins to `silver_dqa_issues.record_id`. File-scoped defects
carry the `source_file_id` in that column. The derivation is documented in
`src/sbfp_platform/synthetic/identity.py`.
"""


# --------------------------------------------------------------------------------------
# Row and file models
# --------------------------------------------------------------------------------------


@dataclass
class RawRow:
    """One data row destined for a source file, before rendering."""

    key: int
    period: str
    school_id: str
    child: world.Child
    #: Literal cell values written in place of the canonical ones. Defects live here, so
    #: the true world stays pristine and the answer key can quote both sides.
    overrides: dict[str, Any] = field(default_factory=dict)
    #: Set on rows that exist only because a row was copy-pasted.
    duplicate_of: int | None = None
    row_number: int = 0
    record_id: str = ""


@dataclass
class SubmissionFile:
    period: str
    school: world.School
    file_type: str
    sheet_name: str
    headers: dict[str, str]
    columns: list[str]
    extra_columns: list[str]
    date_style: str
    sex_style: tuple[str, str]
    grade_style: str
    submitted_on: dt.date
    school_name_written: str
    rows: list[RawRow] = field(default_factory=list)
    path: Path | None = None
    file_id: str = ""


@dataclass
class Defect:
    record_id: str
    field_name: str | None
    defect_type: str
    original_value: str | None
    corrupted_value: str | None


class _Chooser:
    """Hands out disjoint subsets of a row pool in one fixed shuffled order.

    Disjointness is the point. Two defects on the same cell would leave the answer key
    claiming a corruption that the other overwrote, and the scorecard would then charge
    a DQA rule with a miss it could not have avoided.
    """

    def __init__(self, rng: np.random.Generator, pool: list[int]) -> None:
        self._order = [pool[int(i)] for i in rng.permutation(len(pool))]
        self._cursor = 0

    def take(self, count: int) -> list[int]:
        count = max(0, min(count, len(self._order) - self._cursor))
        chunk = self._order[self._cursor : self._cursor + count]
        self._cursor += count
        return chunk

    def take_where(self, count: int, predicate: Callable[[int], bool]) -> list[int]:
        """Take up to ``count`` remaining entries satisfying ``predicate``."""
        chosen: list[int] = []
        remaining: list[int] = []
        for value in self._order[self._cursor :]:
            if len(chosen) < count and predicate(value):
                chosen.append(value)
            else:
                remaining.append(value)
        self._order = self._order[: self._cursor] + remaining
        return chosen

    @property
    def remaining(self) -> list[int]:
        return self._order[self._cursor :]


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def generate_all(config) -> dict[str, int]:
    """Write the messy source tree and the answer key. Returns a summary of counts."""
    rng_for = _stream_factory(int(config.seed))
    config.paths.ensure()
    _clear_previous_output(config)

    the_world = world.build_world(rng_for, config)
    LOGGER.info(
        "world: %d schools, %d children, %d retained",
        len(the_world.schools),
        len(the_world.children),
        sum(1 for child in the_world.children if not child.attrited),
    )

    files = _plan_submission_files(rng_for, config, the_world)

    pending_row_defects = _inject_cell_defects(rng_for, config, the_world, files)
    _inject_duplicates(rng_for, config, files, pending_row_defects)

    # File-scoped defects move a file's submission date, and the submission date is in
    # the filename, which is what the file identity is derived from. So they settle
    # first; only then can any identifier be assigned.
    defects = _inject_file_defects(rng_for, config, files)
    _finalize_identity(config, files)

    rows_by_key = {row.key: row for submission in files for row in submission.rows}
    defects.extend(
        Defect(
            record_id=rows_by_key[row_key].record_id,
            field_name=field_name,
            defect_type=defect_type,
            original_value=original,
            corrupted_value=corrupted,
        )
        for row_key, field_name, defect_type, original, corrupted in pending_row_defects
    )

    for submission in files:
        _write_submission(submission)

    _write_reference_files(rng_for, config, the_world)
    _write_readme(config.paths.raw_data_dir, _RAW_README)

    counts = _write_answer_key(config, the_world, files, defects)
    _write_readme(config.paths.ground_truth_dir, _TRUTH_README)

    counts["raw_files"] = len(files) + 3
    LOGGER.info(
        "wrote %d source files, %d truth children, %d truth links, %d truth defects",
        counts["raw_files"],
        counts["children"],
        counts["links"],
        counts["defects"],
    )
    return counts


def _stream_factory(seed: int) -> Callable[[str], np.random.Generator]:
    """Named substreams off one master seed.

    Naming the streams rather than threading a single generator means a change to how
    schools are drawn cannot silently shift every measurement downstream of it, which
    is what makes the committed regression floors in CI meaningful over time.
    """

    def make(name: str) -> np.random.Generator:
        tag = int(stable_id(name)[:8], 16)
        return np.random.default_rng([seed, tag])

    return make


def _clear_previous_output(config) -> None:
    """Remove files this generator owns, so a profile switch cannot leave stale ones."""
    targets = [config.paths.raw_data_dir, *config.paths.raw_subdirs.values()]
    for directory in targets:
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".xlsx", ".csv", ".md"}:
                path.unlink()
    truth_dir = config.paths.ground_truth_dir
    if truth_dir.is_dir():
        for path in truth_dir.iterdir():
            if path.is_file() and path.suffix in {".parquet", ".md"}:
                path.unlink()


# --------------------------------------------------------------------------------------
# File planning
# --------------------------------------------------------------------------------------


def _plan_submission_files(rng_for, config, the_world: world.World) -> list[SubmissionFile]:
    """Decide format, headers, sheet name, and submission date for every school file."""
    rng = rng_for("files.layout")
    registry = config.schema_registry["datasets"]["school_submission"]["columns"]
    synthetic = config.synthetic
    sheet_variants = list(synthetic["sheet_name_variants"])
    formats, weights = _format_mix(synthetic["file_format_mix"])
    grace = int(config.dqa_thresholds["late_submission_grace_days"])

    windows = {
        "baseline": the_world.baseline_window,
        "endline": the_world.endline_window,
    }

    rows_by_school: dict[tuple[str, str], list[world.Child]] = {}
    for child in the_world.children:
        rows_by_school.setdefault((child.baseline_school_id, "baseline"), []).append(child)
        if not child.attrited and child.endline_school_id is not None:
            rows_by_school.setdefault((child.endline_school_id, "endline"), []).append(child)

    next_key = 0
    files: list[SubmissionFile] = []
    for period in ("baseline", "endline"):
        for school in the_world.schools:
            file_type = str(rng.choice(formats, p=weights))
            droppable = [f for f in _DROPPABLE_FIELDS if rng.random() < 0.18]
            columns = [f for f in _SUBMISSION_FIELDS if f not in droppable]
            # school_name anchors the sheet the way a real form does; the rest drift.
            tail = [c for c in columns if c != "school_name"]
            tail = [tail[int(i)] for i in rng.permutation(len(tail))]
            columns = ["school_name", *tail]

            extra = []
            if rng.random() < 0.35:
                extra.append(str(rng.choice(_UNMAPPED_HEADERS)))

            date_style = str(
                rng.choice(["iso", "native", "slash"] if file_type == "xlsx" else ["iso", "slash"])
            )
            style_index = int(rng.integers(0, len(_SEX_STYLES)))

            window_end = windows[period][1]
            submitted_on = window_end + dt.timedelta(days=int(rng.integers(0, grace)))

            submission = SubmissionFile(
                period=period,
                school=school,
                file_type=file_type,
                sheet_name=str(rng.choice(sheet_variants)),
                headers={
                    canonical: str(rng.choice(registry[canonical]["aliases"]))
                    for canonical in columns
                },
                columns=columns,
                extra_columns=extra,
                date_style=date_style,
                sex_style=_SEX_STYLES[style_index],
                grade_style=str(rng.choice(["long", "short"])),
                submitted_on=submitted_on,
                school_name_written=school.school_name,
            )

            children = rows_by_school.get((school.school_id, period), [])
            order = rng.permutation(len(children))
            for position in order:
                child = children[int(position)]
                submission.rows.append(
                    RawRow(
                        key=next_key,
                        period=period,
                        school_id=school.school_id,
                        child=child,
                    )
                )
                next_key += 1
            files.append(submission)
    return files


def _format_mix(mix: dict[str, float]) -> tuple[list[str], list[float]]:
    formats = sorted(mix)
    total = sum(mix.values())
    return formats, [mix[key] / total for key in formats]


# --------------------------------------------------------------------------------------
# Defect injection
# --------------------------------------------------------------------------------------

PendingDefect = tuple[int, str | None, str, str | None, str | None]


def _inject_cell_defects(
    rng_for, config, the_world: world.World, files: list[SubmissionFile]
) -> list[PendingDefect]:
    """Corrupt individual cells, recording every corruption.

    Baseline is processed before endline because two endline defects
    (``height_decrease`` and the cross-wave inconsistencies) need to know what the
    baseline row already looks like.
    """
    rates = config.issue_rates
    pending: list[PendingDefect] = []
    rows_by_period: dict[str, list[RawRow]] = {"baseline": [], "endline": []}
    for submission in files:
        rows_by_period[submission.period].extend(submission.rows)

    file_of_row: dict[int, SubmissionFile] = {
        row.key: submission for submission in files for row in submission.rows
    }
    baseline_row_of_child: dict[str, RawRow] = {
        row.child.child_id: row for row in rows_by_period["baseline"]
    }

    for period in ("baseline", "endline"):
        rows = rows_by_period[period]
        if not rows:
            continue
        by_key = {row.key: row for row in rows}
        keys = [row.key for row in rows]
        n = len(keys)

        _inject_lrn_defects(rng_for(f"defects.lrn.{period}"), rates, keys, by_key, n, pending)
        _inject_birth_date_defects(
            rng_for(f"defects.birth.{period}"),
            rates,
            keys,
            by_key,
            file_of_row,
            n,
            period,
            pending,
        )
        _inject_sex_defects(
            rng_for(f"defects.sex.{period}"), rates, keys, by_key, file_of_row, n, period, pending
        )
        _inject_height_defects(
            rng_for(f"defects.height.{period}"),
            rates,
            keys,
            by_key,
            baseline_row_of_child,
            n,
            period,
            pending,
        )
        _inject_weight_defects(rng_for(f"defects.weight.{period}"), rates, keys, by_key, n, pending)
        if period == "endline":
            _inject_name_drift(rng_for("defects.name"), rates, keys, by_key, n, pending)

    _inject_digit_heaping(config, the_world, files, pending)
    return pending


def _inject_lrn_defects(rng, rates, keys, by_key, n, pending) -> None:
    chooser = _Chooser(rng, keys)
    for row_key in chooser.take(round(rates["missing_lrn"] * n)):
        row = by_key[row_key]
        row.overrides["lrn"] = None
        pending.append((row_key, "lrn_clean", "missing_lrn", row.child.lrn, None))

    for row_key in chooser.take(round(rates["malformed_lrn"] * n)):
        row = by_key[row_key]
        true_lrn = row.child.lrn
        variants = [
            true_lrn[:-1],
            f"{true_lrn[:4]}-{true_lrn[4:8]}-{true_lrn[8:]}",
            f"{true_lrn}0",
            f"LRN{true_lrn[3:]}",
            true_lrn[:6] + " " + true_lrn[6:],
        ]
        corrupted = str(rng.choice(variants))
        row.overrides["lrn"] = corrupted
        pending.append((row_key, "lrn_clean", "malformed_lrn", true_lrn, corrupted))


def _inject_birth_date_defects(rng, rates, keys, by_key, file_of_row, n, period, pending) -> None:
    chooser = _Chooser(rng, keys)

    for row_key in chooser.take(round(rates["missing_birth_date"] * n)):
        row = by_key[row_key]
        row.overrides["birth_date"] = None
        pending.append(
            (row_key, "birthday_str", "missing_birth_date", row.child.birth_date.isoformat(), None)
        )

    # DD/MM is only genuinely ambiguous when the day could also be a month.
    ambiguous = chooser.take_where(
        round(rates["date_format_ambiguity"] * n),
        lambda key: by_key[key].child.birth_date.day <= 12,
    )
    for row_key in ambiguous:
        row = by_key[row_key]
        birth = row.child.birth_date
        corrupted = f"{birth.day:02d}/{birth.month:02d}/{birth.year}"
        row.overrides["birth_date"] = corrupted
        pending.append(
            (row_key, "birthday_str", "date_format_ambiguity", birth.isoformat(), corrupted)
        )

    for row_key in chooser.take(round(rates["excel_serial_date"] * n)):
        row = by_key[row_key]
        birth = row.child.birth_date
        serial = (birth - EXCEL_EPOCH).days
        # Half arrive as numbers, half as strings. The string form is the one that slips
        # past a naive `pd.to_numeric` guard, so both must exist.
        as_text = bool(rng.random() < 0.5) or file_of_row[row_key].file_type == "csv"
        corrupted: Any = str(serial) if as_text else serial
        row.overrides["birth_date"] = corrupted
        pending.append(
            (row_key, "birthday_str", "excel_serial_date", birth.isoformat(), str(serial))
        )

    for row_key in chooser.take(round(rates["timestamp_suffixed_date"] * n)):
        row = by_key[row_key]
        birth = row.child.birth_date
        corrupted = f"{birth.isoformat()} 00:00:00"
        row.overrides["birth_date"] = corrupted
        pending.append(
            (row_key, "birthday_str", "timestamp_suffixed_date", birth.isoformat(), corrupted)
        )

    for row_key in chooser.take(round(rates["impossible_date"] * n)):
        row = by_key[row_key]
        corrupted = str(rng.choice(_IMPOSSIBLE_DATES))
        row.overrides["birth_date"] = corrupted
        pending.append(
            (
                row_key,
                "birthday_str",
                "impossible_date",
                row.child.birth_date.isoformat(),
                corrupted,
            )
        )

    if period == "endline":
        for row_key in chooser.take(round(rates["birthdate_inconsistent_across_waves"] * n)):
            row = by_key[row_key]
            birth = row.child.birth_date
            shift = int(rng.choice([-400, -180, -31, -1, 1, 31, 180, 400]))
            corrupted = (birth + dt.timedelta(days=shift)).isoformat()
            row.overrides["birth_date"] = corrupted
            pending.append(
                (
                    row_key,
                    "birthday_str",
                    "birthdate_inconsistent_across_waves",
                    birth.isoformat(),
                    corrupted,
                )
            )


def _inject_sex_defects(rng, rates, keys, by_key, file_of_row, n, period, pending) -> None:
    chooser = _Chooser(rng, keys)

    for row_key in chooser.take(round(rates["missing_sex"] * n)):
        row = by_key[row_key]
        row.overrides["sex"] = None
        pending.append((row_key, "sex", "missing_sex", row.child.sex, None))

    if period != "endline":
        return

    for row_key in chooser.take(round(rates["sex_inconsistent_across_waves"] * n)):
        row = by_key[row_key]
        flipped = "Female" if row.child.sex == "Male" else "Male"
        rendered = _render_sex(flipped, file_of_row[row_key].sex_style)
        row.overrides["sex"] = rendered
        pending.append((row_key, "sex", "sex_inconsistent_across_waves", row.child.sex, rendered))


def _inject_height_defects(
    rng, rates, keys, by_key, baseline_row_of_child, n, period, pending
) -> None:
    chooser = _Chooser(rng, keys)

    for row_key in chooser.take(round(rates["missing_height"] * n)):
        row = by_key[row_key]
        row.overrides["height_cm"] = None
        measurement = row.child.measurements[row.period]
        pending.append((row_key, "height_cm", "missing_height", f"{measurement.height_cm:g}", None))

    for row_key in chooser.take(round(rates["implausible_height"] * n)):
        row = by_key[row_key]
        true_height = row.child.measurements[row.period].height_cm
        # Keep range defects directionally safe across waves. A too-high baseline or
        # too-low endline would also manufacture a height decrease, causing the
        # consistency rule to raise a legitimate issue that is absent from the answer
        # key. Baseline values therefore go below the plausible floor; endline values
        # go above the ceiling. Both remain unambiguously detectable by the range rule.
        candidates = (
            [round(true_height / 100, 2), 45.0]
            if period == "baseline"
            else [round(true_height * 2.2, 1), 265.0]
        )
        corrupted = float(rng.choice(candidates))
        row.overrides["height_cm"] = corrupted
        pending.append(
            (
                row_key,
                "height_cm",
                "implausible_height",
                f"{true_height:g}",
                f"{corrupted:g}",
            )
        )

    if period != "endline":
        return

    # A shrinking child is only detectable if the baseline height survived intact.
    decreasing = chooser.take_where(
        round(rates["height_decrease"] * n),
        lambda key: "height_cm" not in baseline_row_of_child[by_key[key].child.child_id].overrides,
    )
    for row_key in decreasing:
        row = by_key[row_key]
        baseline_height = row.child.measurements["baseline"].height_cm
        true_height = row.child.measurements["endline"].height_cm
        # At least 5 cm below baseline, and floored above the implausible-height
        # threshold. The 5 cm is because digit heaping runs after this and may round the
        # baseline row *down* by up to 2.5 cm; a 2 cm drop would then read as a 0.5 cm
        # change, inside the rule's tolerance — an injected defect nobody could detect,
        # scored as a miss against a rule that did nothing wrong. The floor is so the
        # corrupted value does not also trip the implausible-height rule, which would
        # be a false positive for a defect this row never carried.
        corrupted = max(82.0, round(baseline_height - float(rng.uniform(5.0, 12.0)), 1))
        row.overrides["height_cm"] = corrupted
        pending.append(
            (row_key, "height_cm", "height_decrease", f"{true_height:g}", f"{corrupted:g}")
        )


def _inject_weight_defects(rng, rates, keys, by_key, n, pending) -> None:
    chooser = _Chooser(rng, keys)

    for row_key in chooser.take(round(rates["missing_weight"] * n)):
        row = by_key[row_key]
        row.overrides["weight_kg"] = None
        measurement = row.child.measurements[row.period]
        pending.append((row_key, "weight_kg", "missing_weight", f"{measurement.weight_kg:g}", None))

    for row_key in chooser.take(round(rates["implausible_weight"] * n)):
        row = by_key[row_key]
        true_weight = row.child.measurements[row.period].weight_kg
        corrupted = float(
            rng.choice([round(true_weight / 10, 2), round(true_weight * 12, 1), 3.5, 185.0])
        )
        row.overrides["weight_kg"] = corrupted
        pending.append(
            (
                row_key,
                "weight_kg",
                "implausible_weight",
                f"{true_weight:g}",
                f"{corrupted:g}",
            )
        )


def _inject_name_drift(rng, rates, keys, by_key, n, pending) -> None:
    """Endline-only respelling. Marked non-detectable: no rule can tell it from a
    different child, which is exactly why probabilistic linkage has to exist."""
    chooser = _Chooser(rng, keys)
    for row_key in chooser.take(round(rates["name_spelling_drift"] * n)):
        row = by_key[row_key]
        true_name = row.child.name
        corrupted = names.drift_spelling(rng, true_name)
        row.overrides["student_name"] = corrupted
        pending.append((row_key, "student_name_clean", "name_spelling_drift", true_name, corrupted))


def _inject_digit_heaping(config, the_world: world.World, files, pending) -> None:
    """Round every surviving height in a heaping school to the nearest 5 cm.

    Heaping is a property of a school's measuring practice, so it is set at the school
    level and applies to both waves. That also keeps the rounding monotone within a
    child, which is what stops it from manufacturing an apparent height decrease.
    """
    heaping = {school.school_id for school in the_world.schools if school.heaps_digits}
    if not heaping:
        return
    for submission in files:
        if submission.school.school_id not in heaping:
            continue
        for row in submission.rows:
            if "height_cm" in row.overrides:
                continue
            true_height = row.child.measurements[row.period].height_cm
            corrupted = round(true_height / _HEAPING_STEP_CM) * _HEAPING_STEP_CM
            row.overrides["height_cm"] = corrupted
            pending.append(
                (
                    row.key,
                    "height_cm",
                    "digit_heaping",
                    f"{true_height:g}",
                    f"{corrupted:g}",
                )
            )


def _inject_duplicates(rng_for, config, files, pending) -> None:
    """Copy-paste rows back into their own file.

    Sources are restricted to rows carrying no other defect. A duplicate of a corrupted
    row would inherit that corruption, and the DQA engine would then legitimately raise
    a second issue for a defect the answer key recorded once — a false positive charged
    to a rule that did nothing wrong.
    """
    rng = rng_for("defects.duplicates")
    rates = config.issue_rates
    dirty = {entry[0] for entry in pending}
    next_key = 1 + max((row.key for f in files for row in f.rows), default=0)

    total_rows = sum(len(f.rows) for f in files)
    if not total_rows:
        return
    targets = {
        "duplicate_exact_row": round(rates["duplicate_exact_row"] * total_rows),
        "duplicate_lrn_name_variant": round(rates["duplicate_lrn_name_variant"] * total_rows),
    }

    clean = [
        (submission_index, row.key)
        for submission_index, submission in enumerate(files)
        for row in submission.rows
        if row.key not in dirty
    ]
    chooser = _Chooser(rng, list(range(len(clean))))

    for defect_type, count in targets.items():
        for slot in chooser.take(count):
            submission_index, source_key = clean[slot]
            submission = files[submission_index]
            source_position = next(
                i for i, row in enumerate(submission.rows) if row.key == source_key
            )
            source = submission.rows[source_position]
            copy = RawRow(
                key=next_key,
                period=source.period,
                school_id=source.school_id,
                child=source.child,
                overrides=dict(source.overrides),
                duplicate_of=source.key,
            )
            next_key += 1

            original_value: str | None = None
            corrupted_value: str | None = None
            field_name: str | None = None
            if defect_type == "duplicate_lrn_name_variant":
                field_name = "lrn_clean"
                original_value = source.child.name
                corrupted_value = names.drift_spelling(rng, source.child.name)
                copy.overrides["student_name"] = corrupted_value

            insert_at = int(rng.integers(source_position + 1, len(submission.rows) + 1))
            submission.rows.insert(insert_at, copy)
            pending.append((copy.key, field_name, defect_type, original_value, corrupted_value))


def _inject_file_defects(rng_for, config, files: list[SubmissionFile]) -> list[Defect]:
    """File-scoped corruption: a drifted school name, a submission past the deadline.

    Counts use ``max(1, ...)`` so that even the ``tiny`` profile, where the configured
    rate rounds to zero files, still exercises the two file-scoped rules. In ``tiny``
    this over-injects relative to the configured rate; at ``demo`` and ``large`` the
    rate holds.
    """
    rng = rng_for("defects.files")
    rates = config.issue_rates
    grace = int(config.dqa_thresholds["late_submission_grace_days"])
    windows = {
        "baseline": dt.date.fromisoformat(config.project["baseline_window"]["end"]),
        "endline": dt.date.fromisoformat(config.project["endline_window"]["end"]),
    }
    n_files = len(files)
    chooser = _Chooser(rng, list(range(n_files)))
    defects: list[Defect] = []

    drift_targets = chooser.take(max(1, round(rates["school_name_drift"] * n_files)))
    late_targets = chooser.take(max(1, round(rates["late_submission"] * n_files)))

    for index in drift_targets:
        submission = files[index]
        original = submission.school.school_name
        submission.school_name_written = names.drift_school_name(rng, original)

    for index in late_targets:
        submission = files[index]
        deadline = windows[submission.period]
        submission.submitted_on = deadline + dt.timedelta(days=grace + 1 + int(rng.integers(0, 45)))

    # File identity depends on the submission date, which the late-submission defect
    # just changed. Assign paths only after both defects have settled.
    _assign_paths(config, files)

    for index in drift_targets:
        submission = files[index]
        defects.append(
            Defect(
                record_id=submission.file_id,
                field_name="school_name",
                defect_type="school_name_drift",
                original_value=submission.school.school_name,
                corrupted_value=submission.school_name_written,
            )
        )
    for index in late_targets:
        submission = files[index]
        deadline = windows[submission.period]
        defects.append(
            Defect(
                record_id=submission.file_id,
                field_name=None,
                defect_type="late_submission",
                original_value=(deadline + dt.timedelta(days=grace)).isoformat(),
                corrupted_value=submission.submitted_on.isoformat(),
            )
        )
    return defects


# --------------------------------------------------------------------------------------
# Identity assignment and rendering
# --------------------------------------------------------------------------------------


def _assign_paths(config, files: list[SubmissionFile]) -> None:
    raw_root = config.paths.raw_data_dir
    subdirs = config.paths.raw_subdirs
    for submission in files:
        name = (
            f"{submission.period}_{submission.school.school_id}_"
            f"{submission.submitted_on.strftime('%Y%m%d')}.{submission.file_type}"
        )
        submission.path = subdirs[submission.period] / name
        submission.file_id = make_file_id(submission.path, raw_root)


def _finalize_identity(config, files: list[SubmissionFile]) -> None:
    """Assign row numbers and record ids. Must run after every row insertion."""
    if any(submission.path is None for submission in files):
        _assign_paths(config, files)
    for submission in files:
        for position, row in enumerate(submission.rows, start=1):
            row.row_number = position
            row.record_id = make_record_id(submission.file_id, position)


def _render_sex(sex: str, style: tuple[str, str]) -> str:
    return style[0] if sex == "Male" else style[1]


def _render_date(value: dt.date, style: str, file_type: str) -> Any:
    if style == "native" and file_type == "xlsx":
        return value
    if style == "slash" and value.day > 12:
        # Unambiguous only because the day cannot be read as a month.
        return f"{value.month:02d}/{value.day:02d}/{value.year}"
    return value.isoformat()


def _render_row(submission: SubmissionFile, row: RawRow) -> list[Any]:
    child = row.child
    measurement = child.measurements[row.period]
    cells: list[Any] = []
    for canonical in submission.columns:
        if canonical in row.overrides:
            cells.append(row.overrides[canonical])
            continue
        if canonical == "school_name":
            cells.append(submission.school_name_written)
        elif canonical == "school_id":
            cells.append(submission.school.school_id)
        elif canonical == "lrn":
            cells.append(child.lrn)
        elif canonical == "student_name":
            cells.append(child.name)
        elif canonical == "birth_date":
            cells.append(
                _render_date(child.birth_date, submission.date_style, submission.file_type)
            )
        elif canonical == "sex":
            cells.append(_render_sex(child.sex, submission.sex_style))
        elif canonical == "grade":
            cells.append(
                child.grade if submission.grade_style == "long" else child.grade.split()[-1]
            )
        elif canonical == "height_cm":
            cells.append(measurement.height_cm)
        elif canonical == "weight_kg":
            cells.append(measurement.weight_kg)
        elif canonical == "measurement_date":
            cells.append(
                _render_date(measurement.measured_on, submission.date_style, submission.file_type)
            )
    cells.extend(_render_extra(header, row) for header in submission.extra_columns)
    return cells


def _render_extra(header: str, row: RawRow) -> Any:
    """Fill an unmapped column with something a clerk would plausibly have typed."""
    if header == "No.":
        return row.row_number or 0
    # `stable_id`, not `hash`: CPython randomizes string hashing per process, which
    # would make the bytes of every file depend on the interpreter's startup entropy.
    spread = int(stable_id(row.child.child_id)[:6], 16)
    if header == "Section":
        return names.BARANGAY_STEMS[spread % len(names.BARANGAY_STEMS)]
    if header == "Status":
        return "Active" if spread % 20 else "Transferred out"
    if header == "Adviser":
        return f"Teacher {row.school_id[-2:]}"
    return "" if spread % 8 else "for verification"


def _write_submission(submission: SubmissionFile) -> None:
    header = [submission.headers[c] for c in submission.columns] + submission.extra_columns
    rows = [_render_row(submission, row) for row in submission.rows]
    assert submission.path is not None
    write_table(submission.path, submission.file_type, submission.sheet_name, header, rows)
    _stamp_mtime(submission.path, submission.submitted_on)


def _stamp_mtime(path: Path, submitted_on: dt.date) -> None:
    """Set the file's mtime to its submission date.

    The manifest records ``modified_at``, and a wall-clock mtime would make it
    meaningless. Not part of the file's bytes, so it does not affect the determinism
    check either way.
    """
    stamp = dt.datetime.combine(submitted_on, dt.time(9, 0)).timestamp()
    os.utime(path, (stamp, stamp))


# --------------------------------------------------------------------------------------
# Reference datasets
# --------------------------------------------------------------------------------------


def _write_reference_files(rng_for, config, the_world: world.World) -> None:
    rng = rng_for("files.reference")
    registry = config.schema_registry["datasets"]
    subdirs = config.paths.raw_subdirs
    school_year = the_world.school_year
    sheet_variants = list(config.synthetic["sheet_name_variants"])

    baseline_counts: dict[str, int] = {}
    for child in the_world.children:
        baseline_counts[child.baseline_school_id] = (
            baseline_counts.get(child.baseline_school_id, 0) + 1
        )

    # Masterlist.
    master_fields = [
        "school_id",
        "school_name",
        "division",
        "municipality",
        "barangay",
        "urban_rural",
        "treatment_status",
        "matched_pair_id",
    ]
    master_columns = registry["school_masterlist"]["columns"]
    master_header = [str(rng.choice(master_columns[f]["aliases"])) for f in master_fields]
    treatment_labels = config.schema_registry["value_normalization"]["treatment_status"]
    master_rows = [
        [
            school.school_id,
            school.school_name,
            school.division,
            school.municipality,
            school.barangay,
            school.urban_rural,
            str(rng.choice(treatment_labels["1" if school.treatment_status else "0"])),
            school.matched_pair_id,
        ]
        for school in the_world.schools
    ]
    write_table(
        subdirs["reference"] / "school_masterlist.xlsx",
        "xlsx",
        str(rng.choice(sheet_variants)),
        master_header,
        master_rows,
    )

    # Enrollment snapshot.
    enrollment_columns = registry["enrollment_snapshot"]["columns"]
    enrollment_fields = ["school_name", "school_year", "current_enrollment"]
    enrollment_header = [
        str(rng.choice(enrollment_columns[f]["aliases"])) for f in enrollment_fields
    ]
    enrollment: dict[str, int] = {}
    enrollment_rows = []
    for school in the_world.schools:
        base = baseline_counts.get(school.school_id, 0)
        total = int(round(base * float(rng.uniform(1.6, 2.4)))) + 5
        enrollment[school.school_id] = total
        enrollment_rows.append([school.school_name, school_year, total])
    write_table(
        subdirs["enrollment"] / f"enrollment_{school_year}.xlsx",
        "xlsx",
        str(rng.choice(sheet_variants)),
        enrollment_header,
        enrollment_rows,
    )

    # Program allocation. `allocation_lag_share` of schools were allocated against an
    # older, smaller enrollment base — the mechanism behind ration dilution, which the
    # program rule reports on. It is a program finding, not a data defect, so it is
    # deliberately absent from truth_defects.
    allocation_columns = registry["program_allocation"]["columns"]
    allocation_fields = [
        "school_name",
        "school_year",
        "allocated_children",
        "delivery_tranche_count",
    ]
    allocation_header = [
        str(rng.choice(allocation_columns[f]["aliases"])) for f in allocation_fields
    ]
    lag_share = float(config.synthetic["allocation_lag_share"])
    allocation_rows = []
    for school in the_world.schools:
        base = baseline_counts.get(school.school_id, 0)
        lagging = bool(rng.random() < lag_share)
        factor = float(rng.uniform(0.62, 0.86)) if lagging else float(rng.uniform(0.98, 1.06))
        allocation_rows.append(
            [
                school.school_name,
                school_year,
                max(1, int(round(base * factor))),
                int(rng.integers(1, 5)),
            ]
        )
    write_table(
        subdirs["allocation"] / f"allocation_{school_year}.csv",
        "csv",
        "Sheet1",
        allocation_header,
        allocation_rows,
    )


def _write_readme(directory: Path, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "README.md").write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------------------
# The answer key
# --------------------------------------------------------------------------------------


def _write_answer_key(
    config, the_world: world.World, files: list[SubmissionFile], defects: list[Defect]
) -> dict[str, int]:
    out_dir = config.paths.ground_truth_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    children_df = pd.DataFrame(
        [
            {
                "true_child_id": child.child_id,
                "true_lrn": child.lrn,
                "true_name": child.name,
                "true_birth_date": pd.Timestamp(child.birth_date),
                "true_sex": child.sex,
                "baseline_school_id": child.baseline_school_id,
                "endline_school_id": child.endline_school_id,
                "attrited": bool(child.attrited),
                "transferred": bool(child.transferred),
            }
            for child in the_world.children
        ]
    ).astype({"true_birth_date": "datetime64[ns]", "attrited": bool, "transferred": bool})

    # Originals only. A duplicated row is a second record for the same child, and
    # pointing the answer key at it would make the link unfindable by construction.
    originals: dict[tuple[str, str], str] = {}
    for submission in files:
        for row in submission.rows:
            if row.duplicate_of is None:
                originals[(row.child.child_id, row.period)] = row.record_id

    links_df = pd.DataFrame(
        [
            {
                "true_child_id": child.child_id,
                "baseline_record_id": originals[(child.child_id, "baseline")],
                "endline_record_id": originals[(child.child_id, "endline")],
                "transferred": bool(child.transferred),
            }
            for child in the_world.children
            if not child.attrited
        ]
    ).astype({"transferred": bool})

    detectable = config.detectable
    ordered = sorted(
        defects,
        key=lambda d: (d.record_id, d.defect_type, d.field_name or "", d.original_value or ""),
    )
    defects_df = pd.DataFrame(
        [
            {
                "defect_id": stable_id(
                    defect.record_id, defect.defect_type, defect.field_name, index, prefix="DFT-"
                ),
                "record_id": defect.record_id,
                "field_name": defect.field_name,
                "defect_type": defect.defect_type,
                "original_value": defect.original_value,
                "corrupted_value": defect.corrupted_value,
                "expected_detectable": bool(detectable[defect.defect_type]),
            }
            for index, defect in enumerate(ordered)
        ]
    ).astype({"expected_detectable": bool})

    TRUTH_CHILDREN.validate(children_df, lazy=True)
    TRUTH_LINKS.validate(links_df, lazy=True)
    TRUTH_DEFECTS.validate(defects_df, lazy=True)

    children_df.to_parquet(out_dir / "truth_children.parquet", index=False)
    links_df.to_parquet(out_dir / "truth_links.parquet", index=False)
    defects_df.to_parquet(out_dir / "truth_defects.parquet", index=False)

    return {
        "children": len(children_df),
        "links": len(links_df),
        "defects": len(defects_df),
        "rows": sum(len(submission.rows) for submission in files),
    }
