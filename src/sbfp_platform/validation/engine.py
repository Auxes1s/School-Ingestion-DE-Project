"""The rule engine.

Responsibilities, and deliberately nothing else:

* check the registry against ``configs/dqa_rules.yml`` before anything runs;
* hand each rule its frame and a read-only context;
* stamp the config-owned columns (``severity``, ``scope``) and the run-owned columns
  (``issue_id``, ``run_id``, ``resolved_status``, ``detected_at``) onto what comes back;
* assemble a frame that satisfies :data:`sbfp_platform.contracts.SILVER_DQA_ISSUES`.

Rules do not know about the issue schema, and the engine does not know about any rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from sbfp_platform.contracts import SILVER_DQA_ISSUES
from sbfp_platform.utils.hashing import stable_id
from sbfp_platform.utils.logging import get_logger, new_run_id
from sbfp_platform.validation.issues import RECORD_SCOPES, Issue, RuleContext, RuleSpec
from sbfp_platform.validation.registry import RuleImpl, validate_registry

logger = get_logger(__name__)

#: Column order of the issue registry. Matches the contract; extra columns are not added.
ISSUE_COLUMNS = (
    "issue_id",
    "run_id",
    "rule_id",
    "severity",
    "scope",
    "source_file_id",
    "school_id",
    "period",
    "record_id",
    "field_name",
    "observed_value",
    "issue_message",
    "suggested_action",
    "resolved_status",
    "detected_at",
)

_TEXT_COLUMNS = tuple(c for c in ISSUE_COLUMNS if c != "detected_at")

#: Whatever the installed pandas infers for a column of Python strings — a dedicated
#: string dtype on pandas 3, plain object on pandas 2. Casting to it rather than to a
#: hardcoded dtype is what keeps the emitted frame valid against ``Column(str)`` on both.
_STRING_DTYPE = pd.Series(["x"]).dtype

#: Every issue starts unresolved; the resolution workflow is a downstream concern.
_INITIAL_STATUS = "unresolved"


@dataclass(frozen=True)
class RuleOutcome:
    """What happened when the engine tried to run one rule."""

    rule_id: str
    issue_count: int
    skipped_reason: str | None = None

    @property
    def ran(self) -> bool:
        return self.skipped_reason is None


def empty_issue_frame() -> pd.DataFrame:
    """An issue registry with no rows but the right dtypes.

    Needed because a clean dataset is a legitimate outcome, and pandera validates dtypes
    on empty frames too.
    """
    frame = pd.DataFrame({column: pd.Series(dtype=_STRING_DTYPE) for column in _TEXT_COLUMNS})
    frame["detected_at"] = pd.Series(dtype="datetime64[ns]")
    return frame[list(ISSUE_COLUMNS)]


def _missing_frames(impl: RuleImpl, frames: Mapping[str, pd.DataFrame]) -> list[str]:
    return [name for name in impl.frames_needed if name not in frames]


def _row(
    issue: Issue,
    spec: RuleSpec,
    run_id: str,
    detected_at: pd.Timestamp,
    ordinal: int,
) -> dict[str, object]:
    record_id = issue.record_id if spec.scope in RECORD_SCOPES else None
    return {
        "issue_id": stable_id(
            run_id,
            spec.rule_id,
            record_id,
            issue.source_file_id,
            issue.school_id,
            issue.period,
            issue.field_name,
            ordinal,
            prefix="ISS_",
        ),
        "run_id": run_id,
        "rule_id": spec.rule_id,
        # Severity and scope are the config's to decide, never the rule body's.
        "severity": spec.severity,
        "scope": spec.scope,
        "source_file_id": issue.source_file_id,
        "school_id": issue.school_id,
        "period": issue.period,
        "record_id": record_id,
        "field_name": issue.field_name or spec.primary_field,
        "observed_value": issue.observed_value,
        "issue_message": issue.message,
        "suggested_action": issue.suggested_action,
        "resolved_status": _INITIAL_STATUS,
        "detected_at": detected_at,
    }


def evaluate(
    frames: Mapping[str, pd.DataFrame],
    config,
    *,
    run_id: str | None = None,
    detected_at: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, list[RuleOutcome]]:
    """Run every configured rule and assemble the issue registry.

    Args:
        frames: Input tables by name, as loaded by
            :func:`sbfp_platform.validation.frames.load_frames`.
        config: The resolved platform config; supplies rule specs and thresholds.
        run_id: Identifier stamped on every issue. Generated when omitted.
        detected_at: Detection timestamp. Defaults to now.

    Returns:
        The issue registry, validated against ``SILVER_DQA_ISSUES``, and one
        :class:`RuleOutcome` per configured rule.

    Raises:
        RuleRegistryError: if the registry and the rule config disagree.
    """
    implementations = validate_registry(config)
    run_id = run_id or new_run_id("dqa")
    detected_at = detected_at or pd.Timestamp.now().floor("s")

    rows: list[dict[str, object]] = []
    outcomes: list[RuleOutcome] = []

    for raw_spec in config.dqa_rules:
        spec = RuleSpec.from_config(raw_spec)
        impl = implementations[spec.rule_id]

        absent = _missing_frames(impl, frames)
        if absent:
            outcomes.append(
                RuleOutcome(spec.rule_id, 0, skipped_reason=f"input not available: {absent}")
            )
            logger.warning(
                "%s skipped — %s not in the lakehouse. Its detection rate will read as zero.",
                spec.rule_id,
                ", ".join(absent),
            )
            continue

        ctx = RuleContext(
            spec=spec,
            thresholds=config.dqa_thresholds,
            project=config.project,
            schema_registry=config.schema_registry,
            frames=frames,
        )
        issues = list(impl.func(frames[impl.frame], ctx))
        rows.extend(
            _row(issue, spec, run_id, detected_at, ordinal) for ordinal, issue in enumerate(issues)
        )
        outcomes.append(RuleOutcome(spec.rule_id, len(issues)))

    registry_frame = (
        pd.DataFrame(rows, columns=list(ISSUE_COLUMNS)) if rows else empty_issue_frame()
    )
    if rows:
        for column in _TEXT_COLUMNS:
            registry_frame[column] = registry_frame[column].astype(_STRING_DTYPE)
        registry_frame["detected_at"] = pd.to_datetime(registry_frame["detected_at"]).astype(
            "datetime64[ns]"
        )

    return SILVER_DQA_ISSUES.validate(registry_frame), outcomes
