"""Canonical table schemas — the frozen contract between pipeline slices.

Every table written by any slice is declared here. A slice may add rows and may add
columns beyond its declared schema only where the schema sets ``strict=False``; it may
not rename or retype a declared column. Changing anything in this module is a
cross-slice breaking change and requires updating the design spec first.

Naming note: ``lrn_clean``, ``student_name_clean``, ``first_letter_name``,
``birthday_str``, and ``sex`` deliberately reuse the field names from the real LDS II
pipeline (spec §5), so the synthetic problem is recognizably the real problem.
"""

from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema

# --------------------------------------------------------------------------------------
# Shared vocabularies
# --------------------------------------------------------------------------------------

PERIODS = ("baseline", "endline")
SEXES = ("Male", "Female")
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
RESOLUTION_STATES = ("unresolved", "accepted", "corrected", "suppressed")
LINKAGE_METHODS = ("deterministic", "splink", "combined")
ISSUE_SCOPES = ("file", "record", "child", "school", "school_period")

#: Provenance columns every bronze table carries (TDS §11.1). Ingestion writes these;
#: silver models must propagate ``source_file_id`` and ``source_row_number`` so any gold
#: row can be traced back to a cell in a source spreadsheet.
BRONZE_METADATA_COLUMNS = (
    "run_id",
    "source_file_id",
    "source_file_path",
    "source_sheet_name",
    "source_row_number",
    "file_hash",
    "ingested_at",
    "raw_payload_json",
)

_BRONZE_META_SCHEMA = {
    "run_id": Column(str, nullable=False),
    "source_file_id": Column(str, nullable=False),
    "source_file_path": Column(str, nullable=False),
    "source_sheet_name": Column(str, nullable=True),
    "source_row_number": Column("int64", nullable=False),
    "file_hash": Column(str, nullable=False),
    "ingested_at": Column("datetime64[ns]", nullable=False),
    "raw_payload_json": Column(str, nullable=True),
}


# --------------------------------------------------------------------------------------
# Bronze
# --------------------------------------------------------------------------------------

BRONZE_FILE_MANIFEST = DataFrameSchema(
    {
        "source_file_id": Column(str, nullable=False, unique=True),
        "source_file_path": Column(str, nullable=False),
        "file_name": Column(str, nullable=False),
        "file_type": Column(str, pa.Check.isin(["xlsx", "csv"]), nullable=False),
        "dataset": Column(str, nullable=False),
        "file_hash": Column(str, nullable=False),
        "file_size_bytes": Column("int64", nullable=False),
        "modified_at": Column("datetime64[ns]", nullable=False),
        "discovered_at": Column("datetime64[ns]", nullable=False),
        "ingested_at": Column("datetime64[ns]", nullable=True),
        "school_id_guess": Column(str, nullable=True),
        "period_guess": Column(str, nullable=True),
        "run_id": Column(str, nullable=False),
        "status": Column(
            str,
            pa.Check.isin(["ingested", "skipped_unchanged", "failed", "superseded"]),
            nullable=False,
        ),
        "rows_read": Column("int64", nullable=True),
        "rows_written": Column("int64", nullable=True),
        "error_message": Column(str, nullable=True),
    },
    strict=False,
    name="bronze_file_manifest",
)

BRONZE_SCHEMA_DRIFT_LOG = DataFrameSchema(
    {
        "run_id": Column(str, nullable=False),
        "source_file_id": Column(str, nullable=False),
        "dataset": Column(str, nullable=False),
        "column_name_raw": Column(str, nullable=False),
        "drift_type": Column(
            str,
            pa.Check.isin(["unmapped_column", "missing_required", "missing_optional"]),
            nullable=False,
        ),
        "mapped_to": Column(str, nullable=True),
        "detected_at": Column("datetime64[ns]", nullable=False),
    },
    strict=False,
    name="bronze_schema_drift_log",
)


# --------------------------------------------------------------------------------------
# Silver
# --------------------------------------------------------------------------------------

SILVER_CHILD_RECORDS = DataFrameSchema(
    {
        "child_record_id": Column(str, nullable=False, unique=True),
        "school_id": Column(str, nullable=False),
        "period": Column(str, pa.Check.isin(PERIODS), nullable=False),
        "lrn_clean": Column(str, nullable=True),
        "student_name_clean": Column(str, nullable=True),
        "first_letter_name": Column(str, nullable=True),
        "birthday_str": Column(str, nullable=True),
        "sex": Column(str, pa.Check.isin([*SEXES]), nullable=True),
        "grade": Column(str, nullable=True),
        **_BRONZE_META_SCHEMA,
    },
    strict=False,
    name="silver_child_records",
)

SILVER_MEASUREMENTS = DataFrameSchema(
    {
        "measurement_id": Column(str, nullable=False, unique=True),
        "child_record_id": Column(str, nullable=False),
        "school_id": Column(str, nullable=False),
        "period": Column(str, pa.Check.isin(PERIODS), nullable=False),
        "measurement_date": Column("datetime64[ns]", nullable=True),
        "age_years": Column("float64", nullable=True),
        "height_cm": Column("float64", nullable=True),
        "weight_kg": Column("float64", nullable=True),
        "bmi": Column("float64", nullable=True),
        "measurement_quality_flag": Column(str, nullable=True),
    },
    strict=False,
    name="silver_measurements",
)

SILVER_SCHOOLS = DataFrameSchema(
    {
        "school_id": Column(str, nullable=False, unique=True),
        "school_name": Column(str, nullable=False),
        "division": Column(str, nullable=True),
        "municipality": Column(str, nullable=True),
        "barangay": Column(str, nullable=True),
        "urban_rural": Column(str, nullable=True),
        "treatment_status": Column("int64", pa.Check.isin([0, 1]), nullable=False),
        "matched_pair_id": Column(str, nullable=True),
    },
    strict=False,
    name="silver_schools",
)

SILVER_ALLOCATIONS = DataFrameSchema(
    {
        "school_id": Column(str, nullable=False),
        "school_year": Column(str, nullable=False),
        "allocated_children": Column("float64", nullable=True),
        "current_enrollment": Column("float64", nullable=True),
        "nominal_rice_kg_per_child": Column("float64", nullable=True),
        "effective_rice_kg_per_child": Column("float64", nullable=True),
        "dilution_ratio": Column("float64", nullable=True),
        "delivery_tranche_count": Column("float64", nullable=True),
        "delivery_timing_flag": Column(str, nullable=True),
    },
    strict=False,
    name="silver_allocations",
)

#: Row-level issue registry. One row per (record, rule) detection.
SILVER_DQA_ISSUES = DataFrameSchema(
    {
        "issue_id": Column(str, nullable=False, unique=True),
        "run_id": Column(str, nullable=False),
        "rule_id": Column(str, nullable=False),
        "severity": Column(str, pa.Check.isin([*SEVERITIES]), nullable=False),
        "scope": Column(str, pa.Check.isin([*ISSUE_SCOPES]), nullable=False),
        "source_file_id": Column(str, nullable=True),
        "school_id": Column(str, nullable=True),
        "period": Column(str, nullable=True),
        # record_id joins to truth_defects.record_id for the DQA scorecard (spec §3.1).
        "record_id": Column(str, nullable=True),
        "field_name": Column(str, nullable=True),
        "observed_value": Column(str, nullable=True),
        "issue_message": Column(str, nullable=False),
        "suggested_action": Column(str, nullable=True),
        "resolved_status": Column(str, pa.Check.isin([*RESOLUTION_STATES]), nullable=False),
        "detected_at": Column("datetime64[ns]", nullable=False),
    },
    strict=False,
    name="silver_dqa_issues",
)


# --------------------------------------------------------------------------------------
# Linkage
# --------------------------------------------------------------------------------------

LINKAGE_CANDIDATES = DataFrameSchema(
    {
        "candidate_id": Column(str, nullable=False, unique=True),
        "baseline_record_id": Column(str, nullable=False),
        "endline_record_id": Column(str, nullable=False),
        "school_id": Column(str, nullable=True),
        "method": Column(str, pa.Check.isin([*LINKAGE_METHODS]), nullable=False),
        "pass_id": Column(str, nullable=True),
        "match_probability": Column("float64", nullable=True),
        "match_weight": Column("float64", nullable=True),
    },
    strict=False,
    name="silver_linkage_candidates",
)

LINKAGE_RESULTS = DataFrameSchema(
    {
        "link_id": Column(str, nullable=False, unique=True),
        "baseline_record_id": Column(str, nullable=False),
        "endline_record_id": Column(str, nullable=False),
        "school_id": Column(str, nullable=True),
        "method": Column(str, pa.Check.isin([*LINKAGE_METHODS]), nullable=False),
        "match_probability": Column("float64", nullable=True),
        "decision": Column(str, pa.Check.isin(["accepted", "review", "rejected"]), nullable=False),
        "review_reason": Column(str, nullable=True),
        "transferred_flag": Column(bool, nullable=False),
    },
    strict=False,
    name="silver_linkage_results",
)


# --------------------------------------------------------------------------------------
# Ground truth — written by synthetic/, read ONLY by evaluation/ (spec §2.2)
# --------------------------------------------------------------------------------------

TRUTH_CHILDREN = DataFrameSchema(
    {
        "true_child_id": Column(str, nullable=False, unique=True),
        "true_lrn": Column(str, nullable=False),
        "true_name": Column(str, nullable=False),
        "true_birth_date": Column("datetime64[ns]", nullable=False),
        "true_sex": Column(str, pa.Check.isin([*SEXES]), nullable=False),
        "baseline_school_id": Column(str, nullable=False),
        "endline_school_id": Column(str, nullable=True),
        "attrited": Column(bool, nullable=False),
        "transferred": Column(bool, nullable=False),
    },
    strict=False,
    name="truth_children",
)

#: The denominator for linkage recall. Only non-attrited children appear (spec §3.2).
TRUTH_LINKS = DataFrameSchema(
    {
        "true_child_id": Column(str, nullable=False, unique=True),
        "baseline_record_id": Column(str, nullable=False),
        "endline_record_id": Column(str, nullable=False),
        "transferred": Column(bool, nullable=False),
    },
    strict=False,
    name="truth_links",
)

TRUTH_DEFECTS = DataFrameSchema(
    {
        "defect_id": Column(str, nullable=False, unique=True),
        "record_id": Column(str, nullable=False),
        "field_name": Column(str, nullable=True),
        "defect_type": Column(str, nullable=False),
        "original_value": Column(str, nullable=True),
        "corrupted_value": Column(str, nullable=True),
        # False for defects no rule targets; excluded from the detection-rate
        # denominator so the DQA scorecard stays honest (spec §2.1).
        "expected_detectable": Column(bool, nullable=False),
    },
    strict=False,
    name="truth_defects",
)


# --------------------------------------------------------------------------------------
# Gold
# --------------------------------------------------------------------------------------

GOLD_EVALUATION_CHILD_PANEL = DataFrameSchema(
    {
        "panel_child_id": Column(str, nullable=False, unique=True),
        "school_id": Column(str, nullable=False),
        "treatment_status": Column("int64", pa.Check.isin([0, 1]), nullable=False),
        "sex": Column(str, nullable=True),
        "grade_baseline": Column(str, nullable=True),
        "grade_endline": Column(str, nullable=True),
        "height_cm_baseline": Column("float64", nullable=True),
        "height_cm_endline": Column("float64", nullable=True),
        "weight_kg_baseline": Column("float64", nullable=True),
        "weight_kg_endline": Column("float64", nullable=True),
        "bmi_baseline": Column("float64", nullable=True),
        "bmi_endline": Column("float64", nullable=True),
        "elapsed_days": Column("float64", nullable=True),
        "link_method": Column(str, nullable=True),
        "link_probability": Column("float64", nullable=True),
        "has_critical_issue": Column(bool, nullable=False),
    },
    strict=False,
    name="gold_evaluation_child_panel",
)

GOLD_DQA_SCORECARD = DataFrameSchema(
    {
        "rule_id": Column(str, nullable=False, unique=True),
        "severity": Column(str, pa.Check.isin([*SEVERITIES]), nullable=False),
        "injected_count": Column("int64", nullable=False),
        "detected_count": Column("int64", nullable=False),
        "missed_count": Column("int64", nullable=False),
        "false_positive_count": Column("int64", nullable=False),
        "detection_rate": Column("float64", pa.Check.in_range(0, 1), nullable=True),
        "precision": Column("float64", pa.Check.in_range(0, 1), nullable=True),
    },
    strict=False,
    name="gold_dqa_scorecard",
)

GOLD_LINKAGE_SCORECARD = DataFrameSchema(
    {
        "method": Column(str, pa.Check.isin([*LINKAGE_METHODS]), nullable=False),
        "threshold": Column("float64", nullable=False),
        "true_positives": Column("int64", nullable=False),
        "false_positives": Column("int64", nullable=False),
        "false_negatives": Column("int64", nullable=False),
        "precision": Column("float64", pa.Check.in_range(0, 1), nullable=True),
        "recall": Column("float64", pa.Check.in_range(0, 1), nullable=True),
        "f1": Column("float64", pa.Check.in_range(0, 1), nullable=True),
        # The only metric the real pipeline could compute. Kept alongside recall to
        # make the difference visible.
        "match_rate": Column("float64", pa.Check.in_range(0, 1), nullable=True),
        "review_queue_size": Column("int64", nullable=False),
        # Recall on transferred children specifically — exposes the per-school
        # blocking ceiling (spec §3.2).
        "transfer_recall": Column("float64", pa.Check.in_range(0, 1), nullable=True),
    },
    strict=False,
    name="gold_linkage_scorecard",
)

#: Columns forbidden in any gold table or export. Enforced by
#: tests/unit/test_privacy_no_raw_names.py (spec §8).
FORBIDDEN_GOLD_COLUMNS = (
    "student_name_clean",
    "child_name_raw",
    "true_name",
    "true_lrn",
    "lrn_clean",
    "raw_payload_json",
)
