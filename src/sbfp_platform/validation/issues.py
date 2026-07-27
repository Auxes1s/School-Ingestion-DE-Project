"""Value types shared by every DQA rule.

A rule never builds a ``silver_dqa_issues`` row itself. It yields :class:`Issue` values
carrying only what the rule actually observed; the engine stamps ``issue_id``,
``run_id``, ``severity``, ``scope``, ``resolved_status``, and ``detected_at``. That
split is what keeps severity and scope sourced from ``configs/dqa_rules.yml`` rather
than from rule bodies (spec §3.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

#: Scope values whose issues identify a single silver record. For these, ``record_id``
#: must carry the source row's ``child_record_id`` — it is the join key the DQA
#: scorecard uses against ``truth_defects.record_id``.
RECORD_SCOPES = ("record", "child")


@dataclass(frozen=True)
class RuleSpec:
    """One rule as declared in ``configs/dqa_rules.yml``.

    The config is the contract: severity and scope are read from here and never
    hardcoded in a rule body.
    """

    rule_id: str
    description: str
    severity: str
    scope: str
    fields: tuple[str, ...] = ()
    detects: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, raw: Mapping[str, Any]) -> RuleSpec:
        return cls(
            rule_id=raw["rule_id"],
            description=raw.get("description", ""),
            severity=raw["severity"],
            scope=raw["scope"],
            fields=tuple(raw.get("fields") or ()),
            detects=tuple(raw.get("detects") or ()),
        )

    @property
    def primary_field(self) -> str | None:
        """First declared field, used as the default ``field_name`` on emitted issues."""
        return self.fields[0] if self.fields else None


@dataclass(frozen=True)
class Issue:
    """One detection, before the engine stamps the run-level and config-level columns.

    Scope determines which identifier columns a rule fills in:

    ``record``/``child``
        ``record_id`` (the ``child_record_id`` of the offending row), plus ``school_id``
        and ``period`` for context.
    ``file``
        ``source_file_id``; ``record_id`` stays null.
    ``school``
        ``school_id``; ``record_id`` stays null.
    ``school_period``
        ``school_id`` and ``period``; ``record_id`` stays null.
    """

    message: str
    record_id: str | None = None
    source_file_id: str | None = None
    school_id: str | None = None
    period: str | None = None
    field_name: str | None = None
    observed_value: str | None = None
    suggested_action: str | None = None


@dataclass(frozen=True)
class RuleContext:
    """Everything a rule may read besides its own DataFrame.

    Rules are pure: they read this context and their frame, and touch nothing else. No
    rule opens a file, and no rule mutates ``frames``.
    """

    spec: RuleSpec
    thresholds: Mapping[str, Any]
    project: Mapping[str, Any]
    schema_registry: Mapping[str, Any]
    frames: Mapping[str, pd.DataFrame] = field(default_factory=dict)

    def threshold(self, name: str) -> Any:
        """Look up a threshold, failing loudly when the config does not declare it."""
        try:
            return self.thresholds[name]
        except KeyError as exc:  # pragma: no cover - config is frozen and tested
            raise KeyError(
                f"Rule {self.spec.rule_id} needs threshold {name!r}, which is not declared "
                "under `thresholds` in configs/dqa_rules.yml."
            ) from exc

    def frame(self, name: str) -> pd.DataFrame:
        """Look up an auxiliary frame the rule declared via ``requires``."""
        try:
            return self.frames[name]
        except KeyError as exc:  # pragma: no cover - engine checks availability first
            raise KeyError(
                f"Rule {self.spec.rule_id} needs frame {name!r}, which was not loaded. "
                "Declare it in the rule's `requires` so the engine can skip the rule "
                "cleanly when the frame is absent."
            ) from exc


def as_text(value: Any) -> str | None:
    """Render an observed value for the issue registry, preserving 'absent' as null."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NaT:
        return None
    if isinstance(value, str):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)
