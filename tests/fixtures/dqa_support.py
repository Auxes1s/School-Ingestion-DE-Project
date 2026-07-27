"""Running one DQA rule in isolation.

The design constraint on the rule set is that every rule is a pure function over a
DataFrame, which is exactly what makes this helper possible: a test can hand a rule three
rows and read back the issues, with no lakehouse, no engine, and no other rule involved.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from sbfp_platform.config import load_config
from sbfp_platform.validation.issues import Issue, RuleContext, RuleSpec
from sbfp_platform.validation.registry import registry


def config():
    """The tiny-profile config. Rule behavior is profile-independent."""
    return load_config(profile="tiny")


def spec_for(rule_id: str, cfg=None) -> RuleSpec:
    cfg = cfg or config()
    for raw in cfg.dqa_rules:
        if raw["rule_id"] == rule_id:
            return RuleSpec.from_config(raw)
    raise KeyError(f"{rule_id} is not declared in configs/dqa_rules.yml")


def run_rule(rule_id: str, frames: Mapping[str, pd.DataFrame], cfg=None) -> list[Issue]:
    """Invoke one rule against the given frames and return the issues it yields."""
    cfg = cfg or config()
    impl = registry()[rule_id]
    ctx = RuleContext(
        spec=spec_for(rule_id, cfg),
        thresholds=cfg.dqa_thresholds,
        project=cfg.project,
        schema_registry=cfg.schema_registry,
        frames=frames,
    )
    return list(impl.func(frames[impl.frame], ctx))
