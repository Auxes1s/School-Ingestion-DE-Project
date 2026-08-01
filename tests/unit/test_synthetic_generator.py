"""The generator's own contract: determinism, and an answer key that tells the truth. This keeps the test fair. It must work as shown."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from sbfp_platform.config import load_config
from sbfp_platform.contracts import TRUTH_CHILDREN, TRUTH_DEFECTS, TRUTH_LINKS
from sbfp_platform.synthetic.generate import generate_all
from sbfp_platform.synthetic.identity import record_id as make_record_id
from sbfp_platform.synthetic.identity import source_file_id as make_file_id
from sbfp_platform.utils.text import normalize_header

SEED = 2026
PROFILE = "tiny"


# --------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------


def _config_rooted_at(root: Path, seed: int = SEED):
    """A tiny config whose every output path lives under root. This keeps the test fair."""
    base = load_config(profile=PROFILE, seed=seed)
    raw = root / "raw"
    lake = root / "lakehouse"
    paths = replace(
        base.paths,
        raw_data_dir=raw,
        ground_truth_dir=root / "truth",
        lakehouse_dir=lake,
        bronze_dir=lake / "bronze",
        silver_dir=lake / "silver",
        gold_dir=lake / "gold",
        linkage_dir=lake / "linkage",
        duckdb_path=lake / "platform.duckdb",
        outputs_dir=root / "outputs",
        exports_dir=root / "outputs" / "exports",
        reports_dir=root / "outputs" / "reports",
        raw_subdirs={name: raw / name for name in base.paths.raw_subdirs},
    )
    return replace(base, paths=paths, seed=seed)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    root = tmp_path_factory.mktemp("generated")
    config = _config_rooted_at(root)
    counts = generate_all(config=config)
    return config, counts


@pytest.fixture(scope="module")
def truth(generated):
    config, _ = generated
    directory = config.paths.ground_truth_dir
    return {
        "children": pd.read_parquet(directory / "truth_children.parquet"),
        "links": pd.read_parquet(directory / "truth_links.parquet"),
        "defects": pd.read_parquet(directory / "truth_defects.parquet"),
    }


# --------------------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------------------


def _hash_tree(raw_dir: Path) -> dict[str, str]:
    digests = {}
    for path in sorted(raw_dir.rglob("*")):
        if path.is_file():
            digests[path.relative_to(raw_dir).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return digests


def test_same_seed_produces_byte_identical_raw_files(tmp_path):
    """Regenerating must be a no-op at the byte level. This keeps the test fair."""
    first = _config_rooted_at(tmp_path / "a")
    second = _config_rooted_at(tmp_path / "b")
    generate_all(config=first)
    generate_all(config=second)

    left = _hash_tree(first.paths.raw_data_dir)
    right = _hash_tree(second.paths.raw_data_dir)

    assert left.keys() == right.keys(), "The two runs produced different file names."
    differing = sorted(name for name in left if left[name] != right[name])
    assert not differing, f"Byte-level drift in: {differing}"
    assert len(left) > 10, "Suspiciously few files hashed; the tree may be empty."


def test_a_different_seed_produces_different_data(tmp_path):
    """The seed has to actually reach the draws."""
    first = _config_rooted_at(tmp_path / "a", seed=SEED)
    second = _config_rooted_at(tmp_path / "b", seed=SEED + 1)
    generate_all(config=first)
    generate_all(config=second)

    left = pd.read_parquet(first.paths.ground_truth_dir / "truth_children.parquet")
    right = pd.read_parquet(second.paths.ground_truth_dir / "truth_children.parquet")
    assert not left["true_name"].equals(right["true_name"])


# --------------------------------------------------------------------------------------
# Contracts
# --------------------------------------------------------------------------------------


def test_truth_tables_validate_against_their_contracts(truth):
    TRUTH_CHILDREN.validate(truth["children"], lazy=True)
    TRUTH_LINKS.validate(truth["links"], lazy=True)
    TRUTH_DEFECTS.validate(truth["defects"], lazy=True)


def test_readmes_declare_the_data_synthetic(generated):
    config, _ = generated
    for directory in (config.paths.raw_data_dir, config.paths.ground_truth_dir):
        readme = directory / "README.md"
        assert readme.is_file(), f"No README.md in {directory}"
        assert "synthetic" in readme.read_text(encoding="utf-8").lower()


# --------------------------------------------------------------------------------------
# The recall denominator
# --------------------------------------------------------------------------------------


def test_truth_links_excludes_attrited_children(truth):
    children, links = truth["children"], truth["links"]
    attrited = set(children.loc[children["attrited"], "true_child_id"])
    linked = set(links["true_child_id"])

    assert attrited, "No attrition at all — retention must be below 1.0."
    assert not (attrited & linked), (
        f"{len(attrited & linked)} attrited children appear in truth_links. They have no "
        "endline record, so they are true non-matches; including them inflates the "
        "recall denominator and every reported recall figure with it."
    )
    assert linked == set(children.loc[~children["attrited"], "true_child_id"]), (
        "Every non-attrited child must have exactly one link. A retained child missing "
        "from the denominator is a link the scorecard can never credit."
    )


def test_retention_matches_the_configured_rate(generated, truth):
    config, _ = generated
    children = truth["children"]
    observed = float((~children["attrited"]).mean())
    expected = float(config.synthetic["baseline_retention_rate"])
    assert observed == pytest.approx(expected, abs=0.005)


def test_transfers_are_flagged_on_both_tables(generated, truth):
    config, _ = generated
    children, links = truth["children"], truth["links"]

    transferred = children[children["transferred"]]
    assert len(transferred) > 0, "No transfers were generated."
    assert (transferred["baseline_school_id"] != transferred["endline_school_id"]).all(), (
        "A child flagged as transferred must have a different endline school. The "
        "transfer flag enables a separate cross-group recall measure (spec §3.2); if "
        "it does not track the group change it measures nothing."
    )
    assert not transferred["attrited"].any()

    non_transferred = children[~children["transferred"] & ~children["attrited"]]
    assert (non_transferred["baseline_school_id"] == non_transferred["endline_school_id"]).all()

    child_flag = children.set_index("true_child_id")["transferred"]
    aligned = links.set_index("true_child_id")["transferred"]
    assert aligned.equals(child_flag.loc[aligned.index]), (
        "truth_links.transferred disagrees with truth_children.transferred."
    )

    expected = round(float(config.synthetic["transfer_rate"]) * int((~children["attrited"]).sum()))
    assert len(transferred) == expected


def test_link_record_ids_resolve_to_real_rows(generated, truth):
    """Re-derive every raw row's identity from the files and check the links land. This keeps the test fair."""
    config, _ = generated
    known = _all_record_ids(config)
    links = truth["links"]

    missing_baseline = set(links["baseline_record_id"]) - known["baseline"]
    missing_endline = set(links["endline_record_id"]) - known["endline"]
    assert not missing_baseline, f"{len(missing_baseline)} baseline link ids match no raw row."
    assert not missing_endline, f"{len(missing_endline)} endline link ids match no raw row."
    assert links["baseline_record_id"].is_unique
    assert links["endline_record_id"].is_unique


def _all_record_ids(config) -> dict[str, set[str]]:
    raw_root = config.paths.raw_data_dir
    found: dict[str, set[str]] = {"baseline": set(), "endline": set()}
    for period in found:
        for path in sorted(config.paths.raw_subdirs[period].iterdir()):
            if path.suffix not in {".xlsx", ".csv"}:
                continue
            frame = _read_raw(path)
            file_id = make_file_id(path, raw_root)
            found[period].update(
                make_record_id(file_id, position) for position in range(1, len(frame) + 1)
            )
    return found


# --------------------------------------------------------------------------------------
# Defect bookkeeping
# --------------------------------------------------------------------------------------


def test_every_defect_type_is_a_configured_issue_rate(generated, truth):
    config, _ = generated
    injected = set(truth["defects"]["defect_type"])
    configured = set(config.issue_rates)

    assert injected <= configured, (
        f"Injected defect types not in issue_rates: {sorted(injected - configured)}. "
        "The scorecard has no rate to score them against."
    )
    assert injected == configured, (
        f"Configured but never injected: {sorted(configured - injected)}. A rule with an "
        "empty denominator reports an undefined detection rate."
    )


def test_expected_detectable_matches_the_config(generated, truth):
    config, _ = generated
    defects = truth["defects"]
    for defect_type, group in defects.groupby("defect_type"):
        expected = bool(config.detectable[defect_type])
        assert set(group["expected_detectable"]) == {expected}, (
            f"{defect_type} carries the wrong expected_detectable flag."
        )

    non_detectable = defects[~defects["expected_detectable"]]["defect_type"].unique()
    assert set(non_detectable) == {"name_spelling_drift"}, (
        "Only name_spelling_drift is currently undetectable-by-design; anything else "
        "silently dropping out of the detection-rate denominator needs a config change "
        "first."
    )


#: These flaw counts use a fixed share of each row group.
#: The count must match `round(rate * pool)`.
_ROW_RATE_DEFECTS = {
    "missing_lrn": "all",
    "malformed_lrn": "all",
    "missing_birth_date": "all",
    "excel_serial_date": "all",
    "timestamp_suffixed_date": "all",
    "impossible_date": "all",
    "missing_sex": "all",
    "missing_height": "all",
    "implausible_height": "all",
    "missing_weight": "all",
    "implausible_weight": "all",
    "birthdate_inconsistent_across_waves": "endline",
    "sex_inconsistent_across_waves": "endline",
    "name_spelling_drift": "endline",
}


def test_defect_counts_match_the_configured_rates(generated, truth):
    """Injection uses exact-count sampling, not per-row coin flips, so these are equal rather than approximate. which makes the test able to catch a rate that silently stopped being applied. This keeps the test fair. It must work as shown. This check guards the rule."""
    config, _ = generated
    counts = truth["defects"]["defect_type"].value_counts().to_dict()
    pools = _row_pool_sizes(config)

    for defect_type, pool_name in _ROW_RATE_DEFECTS.items():
        rate = config.issue_rates[defect_type]
        expected = sum(round(rate * size) for size in pools[pool_name])
        assert counts.get(defect_type, 0) == expected, (
            f"{defect_type}: injected {counts.get(defect_type, 0)}, expected {expected} "
            f"at rate {rate}."
        )


def test_constrained_defect_counts_stay_near_their_rates(generated, truth):
    """Four defect types cannot hit their rate exactly, and each has a reason. This keeps the test fair."""
    config, _ = generated
    counts = truth["defects"]["defect_type"].value_counts().to_dict()
    total_rows = sum(sum(sizes) for sizes in _row_pool_sizes(config).values() if sizes)
    all_rows = sum(_row_pool_sizes(config)["all"])

    ambiguity_rate = config.issue_rates["date_format_ambiguity"]
    assert counts["date_format_ambiguity"] == pytest.approx(ambiguity_rate * all_rows, rel=0.15)

    heaping_rate = config.issue_rates["digit_heaping"]
    assert 0.2 * heaping_rate * all_rows <= counts["digit_heaping"] <= 4.0 * heaping_rate * all_rows

    assert counts["height_decrease"] > 0
    assert counts["school_name_drift"] > 0
    assert counts["late_submission"] > 0
    assert total_rows > 0


def _row_pool_sizes(config) -> dict[str, list[int]]:
    """Row counts per period, excluding the copy rows injected afterwards. This keeps the test fair. It must work as shown. This check guards the rule."""
    children = pd.read_parquet(config.paths.ground_truth_dir / "truth_children.parquet")
    baseline = len(children)
    endline = int((~children["attrited"]).sum())
    return {"all": [baseline, endline], "endline": [endline], "baseline": [baseline]}


def test_defect_ids_are_unique_and_records_resolve(generated, truth):
    config, _ = generated
    defects = truth["defects"]
    assert defects["defect_id"].is_unique

    known = _all_record_ids(config)
    row_ids = known["baseline"] | known["endline"]
    file_ids = {
        make_file_id(path, config.paths.raw_data_dir)
        for period in ("baseline", "endline")
        for path in config.paths.raw_subdirs[period].iterdir()
        if path.suffix in {".xlsx", ".csv"}
    }
    unresolved = set(defects["record_id"]) - row_ids - file_ids
    assert not unresolved, (
        f"{len(unresolved)} defects point at a record_id that is neither a raw row nor a "
        "source file. The DQA scorecard joins on this column; unresolvable ids become "
        "permanent misses."
    )


# --------------------------------------------------------------------------------------
# No unrecorded defects
# --------------------------------------------------------------------------------------

_ALIAS_MAP: dict[str, str] | None = None


def _alias_map(config) -> dict[str, str]:
    global _ALIAS_MAP
    if _ALIAS_MAP is None:
        columns = config.schema_registry["datasets"]["school_submission"]["columns"]
        _ALIAS_MAP = {
            normalize_header(alias): spec["canonical"]
            for spec in columns.values()
            for alias in spec["aliases"]
        }
    return _ALIAS_MAP


def _read_raw(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path, dtype=object, keep_default_na=True)
    return pd.read_excel(path, sheet_name=0)


def _blank(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or value == ""


_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _classify_birth_date(value, birth_year_min: int, birth_year_max: int) -> str | None:
    """Name the defect a DQA rule would raise for this cell, or None if it is clean."""
    if _blank(value):
        return "missing_birth_date"
    if isinstance(value, dt.date | dt.datetime | pd.Timestamp):
        return None
    if isinstance(value, int | float):
        return "excel_serial_date"
    text = str(value).strip()
    if text.isdigit():
        return "excel_serial_date"
    if " 00:00:00" in text:
        return "timestamp_suffixed_date"
    slash = _SLASH.match(text)
    if slash:
        first, second, _year = (int(part) for part in slash.groups())
        return "date_format_ambiguity" if first <= 12 and second <= 12 else None
    if _ISO.match(text):
        year, month, day = (int(part) for part in text.split("-"))
        try:
            dt.date(year, month, day)
        except ValueError:
            return "impossible_date"
        return None if birth_year_min <= year <= birth_year_max else "impossible_date"
    return "impossible_date"


def test_no_unrecorded_defect_survives_in_the_raw_data(generated, truth):
    """Walk the raw files and confirm the answer key already knows about every cell a DQA rule would flag. This keeps the test fair."""
    config, _ = generated
    defects = truth["defects"]
    recorded: set[tuple[str, str]] = set(
        zip(defects["record_id"], defects["defect_type"], strict=True)
    )
    thresholds = config.dqa_thresholds
    year_min = int(config.project["birth_year_min"])
    year_max = int(config.project["birth_year_max"])
    alias_map = _alias_map(config)

    unrecorded: list[str] = []
    for period in ("baseline", "endline"):
        for path in sorted(config.paths.raw_subdirs[period].iterdir()):
            if path.suffix not in {".xlsx", ".csv"}:
                continue
            frame = _read_raw(path)
            frame = frame.rename(
                columns={
                    column: alias_map[normalize_header(column)]
                    for column in frame.columns
                    if normalize_header(column) in alias_map
                }
            )
            file_id = make_file_id(path, config.paths.raw_data_dir)

            for position, (_, row) in enumerate(frame.iterrows(), start=1):
                rid = make_record_id(file_id, position)

                def flag(
                    defect_type: str,
                    detail: str,
                    rid: str = rid,
                    path: Path = path,
                    position: int = position,
                ) -> None:
                    if (rid, defect_type) not in recorded:
                        unrecorded.append(f"{path.name} row {position}: {defect_type} ({detail})")

                lrn = row.get("lrn_clean")
                if _blank(lrn):
                    flag("missing_lrn", "blank")
                elif not re.fullmatch(r"\d{12}", str(lrn).strip().removesuffix(".0")):
                    flag("malformed_lrn", str(lrn))

                birth_defect = _classify_birth_date(row.get("birthday_str"), year_min, year_max)
                if birth_defect:
                    flag(birth_defect, str(row.get("birthday_str")))

                if _blank(row.get("sex")):
                    flag("missing_sex", "blank")

                for field, bounds_key, missing_type, range_type in (
                    ("height_cm", "height_cm", "missing_height", "implausible_height"),
                    ("weight_kg", "weight_kg", "missing_weight", "implausible_weight"),
                ):
                    value = row.get(field)
                    if _blank(value):
                        flag(missing_type, "blank")
                        continue
                    numeric = float(value)
                    bounds = thresholds[bounds_key]
                    if not bounds["min"] <= numeric <= bounds["max"]:
                        flag(range_type, f"{numeric:g}")

    assert not unrecorded, (
        f"{len(unrecorded)} raw cells would trip a DQA rule but are absent from the answer "
        "key, so each would be scored as a false positive against a rule that was right. "
        f"First few: {unrecorded[:8]}"
    )


def test_recorded_height_decreases_are_actually_detectable(generated, truth):
    """Every injected height decrease must clear the rule's tolerance once the value reaches the file. otherwise it is an injected defect that no rule could ever catch, scored as a miss. This keeps the test fair. It must work as shown."""
    config, _ = generated
    tolerance = float(config.dqa_thresholds["height_decrease_tolerance_cm"])
    heights = _heights_by_record(config)
    links = truth["links"]
    defects = truth["defects"]
    decreased = set(defects.loc[defects["defect_type"] == "height_decrease", "record_id"])

    assert decreased, "No height_decrease defects were injected."
    checked = 0
    for _, link in links.iterrows():
        if link["endline_record_id"] not in decreased:
            continue
        before = heights.get(link["baseline_record_id"])
        after = heights.get(link["endline_record_id"])
        assert before is not None and after is not None
        assert before - after > tolerance, (
            f"Injected height decrease for {link['true_child_id']} reads as "
            f"{before - after:.1f} cm, inside the {tolerance} cm tolerance."
        )
        checked += 1
    assert checked == len(decreased)


def test_honest_children_never_look_like_a_height_decrease(generated, truth):
    """The converse. Digit heaping rounds heights to the nearest 5 cm, and if growth were small enough that rounding could reverse it, honest children would register as injected defects the answer key never recorded. This keeps the test fair. It must work as shown. This check guards the rule. This keeps the test fair."""
    config, _ = generated
    tolerance = float(config.dqa_thresholds["height_decrease_tolerance_cm"])
    heights = _heights_by_record(config)
    defects = truth["defects"]
    decreased = set(defects.loc[defects["defect_type"] == "height_decrease", "record_id"])

    offenders = []
    for _, link in truth["links"].iterrows():
        if link["endline_record_id"] in decreased:
            continue
        before = heights.get(link["baseline_record_id"])
        after = heights.get(link["endline_record_id"])
        if before is None or after is None:
            continue
        if before - after > tolerance:
            offenders.append((link["true_child_id"], before, after))
    assert not offenders, (
        f"{len(offenders)} children shrank without an injected defect: {offenders[:5]}"
    )


def _heights_by_record(config) -> dict[str, float]:
    alias_map = _alias_map(config)
    heights: dict[str, float] = {}
    for period in ("baseline", "endline"):
        for path in sorted(config.paths.raw_subdirs[period].iterdir()):
            if path.suffix not in {".xlsx", ".csv"}:
                continue
            frame = _read_raw(path)
            frame = frame.rename(
                columns={
                    column: alias_map[normalize_header(column)]
                    for column in frame.columns
                    if normalize_header(column) in alias_map
                }
            )
            file_id = make_file_id(path, config.paths.raw_data_dir)
            for position, (_, row) in enumerate(frame.iterrows(), start=1):
                value = row.get("height_cm")
                if not _blank(value):
                    heights[make_record_id(file_id, position)] = float(value)
    return heights


def test_exact_duplicate_rows_are_all_recorded(generated, truth):
    """A row byte-identical to an earlier one in the same file must be in the answer key. This keeps the test fair."""
    config, _ = generated
    defects = truth["defects"]
    recorded = set(defects.loc[defects["defect_type"] == "duplicate_exact_row", "record_id"])

    found: set[str] = set()
    for period in ("baseline", "endline"):
        for path in sorted(config.paths.raw_subdirs[period].iterdir()):
            if path.suffix not in {".xlsx", ".csv"}:
                continue
            frame = _read_raw(path).astype(str)
            file_id = make_file_id(path, config.paths.raw_data_dir)
            seen: set[tuple] = set()
            for position, (_, row) in enumerate(frame.iterrows(), start=1):
                signature = tuple(row.tolist())
                if signature in seen:
                    found.add(make_record_id(file_id, position))
                seen.add(signature)

    assert found, "No exact duplicate rows found in the raw files."
    assert found == recorded, (
        f"Duplicate rows in the files but not the answer key: {sorted(found - recorded)[:5]}; "
        f"recorded but not found: {sorted(recorded - found)[:5]}."
    )


def test_submitted_school_names_match_the_masterlist_unless_recorded(generated, truth):
    config, _ = generated
    defects = truth["defects"]
    drifted = set(defects.loc[defects["defect_type"] == "school_name_drift", "record_id"])

    masterlist = pd.read_excel(
        config.paths.raw_subdirs["reference"] / "school_masterlist.xlsx", sheet_name=0
    )
    known = {str(value) for value in masterlist.iloc[:, 1]}

    offenders = []
    for period in ("baseline", "endline"):
        for path in sorted(config.paths.raw_subdirs[period].iterdir()):
            if path.suffix not in {".xlsx", ".csv"}:
                continue
            frame = _read_raw(path)
            column = next(
                c
                for c in frame.columns
                if _alias_map(config).get(normalize_header(c)) == "school_name"
            )
            written = str(frame[column].iloc[0])
            file_id = make_file_id(path, config.paths.raw_data_dir)
            if written not in known and file_id not in drifted:
                offenders.append((path.name, written))
    assert not offenders, f"Unrecorded school-name drift: {offenders}"
    assert drifted, "No school-name drift was injected."


def test_unmapped_columns_exist_so_drift_logging_has_something_to_log(generated):
    config, _ = generated
    alias_map = _alias_map(config)
    unmapped = 0
    for period in ("baseline", "endline"):
        for path in sorted(config.paths.raw_subdirs[period].iterdir()):
            if path.suffix not in {".xlsx", ".csv"}:
                continue
            frame = _read_raw(path)
            unmapped += sum(
                1 for column in frame.columns if normalize_header(column) not in alias_map
            )
    assert unmapped > 0, (
        "No unmapped columns anywhere. Slice 3's schema-drift log would have nothing to "
        "capture, and the drift-handling path would go untested end to end."
    )


def test_both_file_formats_and_several_sheet_names_appear(generated):
    config, _ = generated
    suffixes = set()
    sheets = set()
    for period in ("baseline", "endline"):
        for path in sorted(config.paths.raw_subdirs[period].iterdir()):
            suffixes.add(path.suffix)
            if path.suffix == ".xlsx":
                sheets.add(pd.ExcelFile(path).sheet_names[0])
    assert suffixes == {".xlsx", ".csv"}
    assert len(sheets) > 1, f"Only one sheet name in use: {sheets}"
