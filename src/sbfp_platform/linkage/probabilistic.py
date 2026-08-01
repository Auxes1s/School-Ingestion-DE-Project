"""Train, persist, load, and run one global Splink model with DuckDB."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import splink.comparison_library as comparison_library
from splink import DuckDBAPI, Linker, SettingsCreator

from sbfp_platform.linkage._frames import CANDIDATE_COLUMNS, typed_frame
from sbfp_platform.utils.hashing import stable_id
from sbfp_platform.utils.logging import get_logger

logger = get_logger(__name__)

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
    if method == "date_of_birth":
        return comparison_library.DateOfBirthComparison(
            column,
            input_is_string=True,
            datetime_thresholds=thresholds,
            datetime_metrics=spec.get("metrics", ["month", "year", "year"]),
            datetime_format="%Y-%m-%d",
        )
    raise ValueError(f"Unsupported Splink comparison method {method!r} for {column!r}")


def _settings(config: dict[str, Any], baseline_count: int, endline_count: int) -> SettingsCreator:
    prior = min(0.1, max(0.001, 1.0 / max(baseline_count, endline_count, 1)))
    return SettingsCreator(
        link_type="link_only",
        unique_id_column_name="child_record_id",
        comparisons=[_comparison(item) for item in config.get("comparisons", [])],
        blocking_rules_to_generate_predictions=list(config.get("prediction_blocking_rules", [])),
        probability_two_random_records_match=prior,
        retain_matching_columns=True,
        retain_intermediate_calculation_columns=True,
        linker_uid=str(config.get("model_uid", "measured_trust_splink_v1")),
    )


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in _INPUT_COLUMNS:
        if column not in result:
            result[column] = pd.NA
    result = result[list(_INPUT_COLUMNS)]
    return result.astype(object).where(result.notna(), None)


def train_splink_model(
    baseline: pd.DataFrame,
    endline: pd.DataFrame,
    config: dict[str, Any],
    model_path: Path,
) -> Path:
    """Train one global Splink model and persist it before inference."""
    if config.get("backend") != "duckdb" or config.get("scope") != "global":
        raise ValueError("Linkage requires probabilistic.backend=duckdb and scope=global")
    if baseline.empty or endline.empty:
        raise ValueError("Splink training requires non-empty baseline and endline records")

    linker = Linker(
        [_prepare(baseline), _prepare(endline)],
        _settings(config, len(baseline), len(endline)),
        DuckDBAPI(),
        input_table_aliases=["baseline", "endline"],
        set_up_basic_logging=False,
    )
    seed = int(config.get("random_seed", 42))
    linker.training.estimate_u_using_random_sampling(
        max_pairs=int(config.get("u_max_pairs", 200_000)), seed=seed
    )
    training_rules = list(config.get("em_training_rules", []))
    if not training_rules:
        raise ValueError("At least one probabilistic.em_training_rules entry is required")
    for rule in training_rules:
        try:
            linker.training.estimate_parameters_using_expectation_maximisation(rule)
        except Exception as exc:
            raise RuntimeError(f"Splink EM training failed for rule {rule!r}") from exc

    model_path.parent.mkdir(parents=True, exist_ok=True)
    linker.misc.save_model_to_json(str(model_path), overwrite=True)
    logger.info("Trained Splink model written to %s", model_path)
    return model_path


def generate_splink_candidates(
    baseline: pd.DataFrame,
    endline: pd.DataFrame,
    config: dict[str, Any],
    model_path: Path,
) -> pd.DataFrame:
    """Load the persisted trained model and score global candidate pairs."""
    if config.get("backend") != "duckdb" or config.get("scope") != "global":
        raise ValueError("Linkage requires probabilistic.backend=duckdb and scope=global")
    if not model_path.is_file():
        raise FileNotFoundError(f"Missing trained Splink model: {model_path}")

    def duplicate_identifier_records(frame: pd.DataFrame) -> set[str]:
        lrn = frame["lrn_clean"].astype("string")
        valid = lrn.notna() & lrn.str.strip().ne("")
        duplicated = valid & lrn.duplicated(keep=False)
        return set(frame.loc[duplicated, "child_record_id"].astype(str))

    ambiguous_baseline = duplicate_identifier_records(baseline)
    ambiguous_endline = duplicate_identifier_records(endline)
    rows: list[dict] = []
    linker = Linker(
        [_prepare(baseline), _prepare(endline)],
        model_path,
        DuckDBAPI(),
        input_table_aliases=["baseline", "endline"],
        set_up_basic_logging=False,
    )
    predictions = linker.inference.predict(threshold_match_probability=0.0)
    predicted = predictions.as_pandas_dataframe()
    for item in predicted.to_dict("records"):
        probability = float(item["match_probability"])
        weight = float(item["match_weight"])
        if not math.isfinite(probability) or not math.isfinite(weight):
            continue
        baseline_id = str(item["child_record_id_l"])
        endline_id = str(item["child_record_id_r"])
        baseline_school = str(item["school_id_l"])
        endline_school = str(item["school_id_r"])
        baseline_lrn = item.get("lrn_clean_l")
        endline_lrn = item.get("lrn_clean_r")
        exact_duplicated_lrn = (
            pd.notna(baseline_lrn)
            and str(baseline_lrn).strip() != ""
            and str(baseline_lrn) == str(endline_lrn)
            and (baseline_id in ambiguous_baseline or endline_id in ambiguous_endline)
        )
        rows.append(
            {
                "candidate_id": stable_id("candidate", "splink", baseline_id, endline_id),
                "baseline_record_id": baseline_id,
                "endline_record_id": endline_id,
                "school_id": baseline_school,
                "method": "splink",
                "pass_id": None,
                "match_probability": probability,
                "match_weight": weight,
                "baseline_school_id": baseline_school,
                "endline_school_id": endline_school,
                "ambiguous": bool(exact_duplicated_lrn),
            }
        )
    predictions.drop_table_from_database_and_remove_from_cache()

    result = typed_frame(rows, CANDIDATE_COLUMNS)
    return result.sort_values(
        ["match_probability", "baseline_record_id", "endline_record_id"],
        ascending=[False, True, True],
        kind="stable",
    ).reset_index(drop=True)
