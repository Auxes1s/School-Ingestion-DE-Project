"""Rule registration. Configs/dqa_rules.yml is the contract. This module is the lookup from a declared rule_id to the function that implements it. Use this rule as shown. Use this rule as shown."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

import pandas as pd

from sbfp_platform.validation.issues import Issue, RuleContext

# A rule is a pure call from a frame and context to a list of issues.
RuleFunc = Callable[[pd.DataFrame, RuleContext], Iterable[Issue]]


class RuleRegistryError(RuntimeError):
    """The rule list and configs/dqa_rules.yml disagree. Use this rule as shown."""


@dataclass(frozen=True)
class RuleImpl:
    """A registered rule and the frames it needs."""

    rule_id: str
    frame: str
    func: RuleFunc
    requires: tuple[str, ...] = ()

    @property
    def frames_needed(self) -> tuple[str, ...]:
        return (self.frame, *self.requires)


_REGISTRY: dict[str, RuleImpl] = {}


def rule(
    rule_id: str, *, frame: str, requires: Iterable[str] = ()
) -> Callable[[RuleFunc], RuleFunc]:
    """Register func as the code of rule_id."""

    def decorator(func: RuleFunc) -> RuleFunc:
        if rule_id in _REGISTRY:
            raise RuleRegistryError(
                f"Rule {rule_id!r} is already registered by "
                f"{_REGISTRY[rule_id].func.__module__}.{_REGISTRY[rule_id].func.__qualname__}. "
                "Each rule_id has exactly one implementation."
            )
        _REGISTRY[rule_id] = RuleImpl(
            rule_id=rule_id, frame=frame, func=func, requires=tuple(requires)
        )
        return func

    return decorator


def registry() -> Mapping[str, RuleImpl]:
    """Every listed rule, keyed by rule_id. Use this rule as shown."""
    from sbfp_platform.validation import rules  # noqa: F401  (import registers the rules)

    return MappingProxyType(_REGISTRY)


def validate_registry(config) -> Mapping[str, RuleImpl]:
    """Assert the rule list and the set rule set are the same set."""
    implemented = registry()
    configured = {raw["rule_id"] for raw in config.dqa_rules}

    unimplemented = sorted(configured - set(implemented))
    unconfigured = sorted(set(implemented) - configured)

    problems = []
    if unimplemented:
        problems.append(
            f"declared in configs/dqa_rules.yml with no implementation: {unimplemented}"
        )
    if unconfigured:
        problems.append(f"implemented but not declared in configs/dqa_rules.yml: {unconfigured}")
    if problems:
        raise RuleRegistryError(
            "DQA rule registry does not match the rule config — " + "; ".join(problems) + "."
        )
    return implemented
