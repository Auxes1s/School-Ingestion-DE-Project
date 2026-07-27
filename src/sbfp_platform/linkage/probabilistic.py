"""Per-school probabilistic linkage powered by Splink 4 and DuckDB."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import splink.comparison_library as comparison_library
from splink import DuckDBAPI, Linker, SettingsCreator

from sbfp_platform.linkage._frames import CANDIDATE_COLUMNS, typed_frame
from sbfp_platform.utils.hashing import stable_id

_INPUT_COLUMNS = (
    "child_record_id",
    "school_id",
    "lrn_clean",
    "student_name_clean",
    "first_letter_name",
    "birthday_str",
    "sex",
    "grade",
)


def _comparison(spec: dict[str, Any]):
    column = spec["column"]
    method = spec["method"]
    thresholds = spec.get("thresholds", [])
    if method == "exact":
        return comparison_library.ExactMatch(column)
    if method == "jaro_winkler":
        return comparison_library.NameComparison(column, jaro_winkler_thresholds=thresholds)
    if method == "levenshtein":
        return comparison_library.LevenshteinAtThresholds(column, thresholds)
    raise ValueError(f"Unsupported Splink comparison method {method!r} for {column!r}")


def _settings(config: dict[str, Any], baseline_count: int, endline_count: int) -> SettingsCreator:
    prior = min(0.1, max(0.001, 1.0 / max(baseline_count, endline_count, 1)))
    return SettingsCreator(
        link_type="link_only",
        unique_id_column_name="child_record_id",
        comparisons=[_comparison(item) for item in config.get("comparisons", [])],
        blocking_rules_to_generate_predictions=list(config.get("blocking_rules", [])),
        probability_two_random_records_match=prior,
        retain_matching_columns=True,
        retain_intermediate_calculation_columns=True,
    )


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in _INPUT_COLUMNS:
        if column not in result:
            result[column] = pd.NA
    result = result[list(_INPUT_COLUMNS)]
    return result.astype(object).where(result.notna(), None)


def _fit_model(linker: Linker, config: dict[str, Any], pair_count: int) -> None:
    """Train when identifiable; tiny groups retain Splink's documented defaults."""
    if pair_count < 4:
        return
    seed = int(config.get("random_seed", 42))
    fraction = float(config.get("em_sample_fraction", 0.1))
    linker.training.estimate_u_using_random_sampling(
        max_pairs=max(1_000, int(pair_count * fraction)), seed=seed
    )
    for rule in config.get("blocking_rules", []):
        try:
            linker.training.estimate_parameters_using_expectation_maximisation(rule)
        except Exception:  # Sparse comparison levels raise backend-specific errors.
            continue


def generate_splink_candidates(
    baseline: pd.DataFrame, endline: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Generate candidates with a fresh in-memory ``DuckDBAPI`` per school."""
    if config.get("backend") != "duckdb" or config.get("scope") != "per_school":
        raise ValueError("Linkage requires probabilistic.backend=duckdb and scope=per_school")

    rows: list[dict] = []
    schools = sorted(set(baseline["school_id"].dropna()) & set(endline["school_id"].dropna()))
    for school_id in schools:
        left = baseline.loc[baseline["school_id"] == school_id]
        right = endline.loc[endline["school_id"] == school_id]
        if left.empty or right.empty:
            continue
        db_api = DuckDBAPI()  # Must remain inside the loop: no cross-school state.
        linker = Linker(
            [_prepare(left), _prepare(right)],
            _settings(config, len(left), len(right)),
            db_api,
            input_table_aliases=["baseline", "endline"],
            set_up_basic_logging=False,
        )
        _fit_model(linker, config, len(left) * len(right))
        predictions = linker.inference.predict(threshold_match_probability=0.0)
        predicted = predictions.as_pandas_dataframe()
        for item in predicted.to_dict("records"):
            probability = float(item["match_probability"])
            weight = float(item["match_weight"])
            if not math.isfinite(probability) or not math.isfinite(weight):
                continue
            baseline_id = str(item["child_record_id_l"])
            endline_id = str(item["child_record_id_r"])
            rows.append(
                {
                    "candidate_id": stable_id("candidate", "splink", baseline_id, endline_id),
                    "baseline_record_id": baseline_id,
                    "endline_record_id": endline_id,
                    "school_id": str(school_id),
                    "method": "splink",
                    "pass_id": None,
                    "match_probability": probability,
                    "match_weight": weight,
                    "baseline_school_id": str(school_id),
                    "endline_school_id": str(school_id),
                    "ambiguous": False,
                }
            )
        predictions.drop_table_from_database_and_remove_from_cache()

    result = typed_frame(rows, CANDIDATE_COLUMNS)
    return result.sort_values(
        ["match_probability", "baseline_record_id", "endline_record_id"],
        ascending=[False, True, True],
        kind="stable",
    ).reset_index(drop=True)
