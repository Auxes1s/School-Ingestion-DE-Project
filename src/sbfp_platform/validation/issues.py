"""Value types shared by every DQA rule. Use this rule as shown."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# These scopes point to one silver row. Their ``record_id`` must hold the source
# ``child_record_id``. The DQA score uses it to join to ``truth_defects.record_id``.
RECORD_SCOPES = ("record", "child")


@dataclass(frozen=True)
class RuleSpec:
    """One rule as declared in configs/dqa_rules.yml. Use this rule as shown."""

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
        """First declared field, used as the default field_name on emitted issues. Use this rule as shown. Use this rule as shown."""
        return self.fields[0] if self.fields else None


@dataclass(frozen=True)
class Issue:
    """One detection, before the engine stamps the run-level and config-level columns. Use this rule as shown. Use this rule as shown. Keep this rule in place."""

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
        """Look up a limit, failing loudly when the config does not declare it. Use this rule as shown."""
        try:
            return self.thresholds[name]
        except KeyError as exc:  # pragma: no cover - config is frozen and tested
            raise KeyError(
                f"Rule {self.spec.rule_id} needs threshold {name!r}, which is not declared "
                "under `thresholds` in configs/dqa_rules.yml."
            ) from exc

    def frame(self, name: str) -> pd.DataFrame:
        """Look up a helper frame the rule declared via requires. Use this rule as shown."""
        try:
            return self.frames[name]
        except KeyError as exc:  # pragma: no cover - engine checks availability first
            raise KeyError(
                f"Rule {self.spec.rule_id} needs frame {name!r}, which was not loaded. "
                "Declare it in the rule's `requires` so the engine can skip the rule "
                "cleanly when the frame is absent."
            ) from exc


def as_text(value: Any) -> str | None:
    """Render an observed value for the issue rule list, preserving 'absent' as null. Use this rule as shown."""
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
