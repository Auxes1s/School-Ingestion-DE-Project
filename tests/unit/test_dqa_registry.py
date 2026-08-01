"""The rule rule list and configs/dqa_rules.yml must describe the same rule set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from sbfp_platform.config import load_config
from sbfp_platform.validation.frames import FRAME_SOURCES
from sbfp_platform.validation.registry import RuleRegistryError, registry, validate_registry


@pytest.fixture(scope="module")
def cfg():
    return load_config(profile="tiny")


@dataclass
class FakeConfig:
    """Minimal stand-in so rule list mismatches can be tested without editing the config. This keeps the test fair. It must work as shown."""

    dqa_rules: list[dict[str, Any]]


def test_every_configured_rule_has_an_implementation(cfg) -> None:
    unimplemented = sorted({raw["rule_id"] for raw in cfg.dqa_rules} - set(registry()))
    assert not unimplemented, (
        f"Rules declared in configs/dqa_rules.yml with no implementation: {unimplemented}."
    )


def test_every_implementation_is_a_configured_rule(cfg) -> None:
    unconfigured = sorted(set(registry()) - {raw["rule_id"] for raw in cfg.dqa_rules})
    assert not unconfigured, (
        f"Implemented rules absent from configs/dqa_rules.yml: {unconfigured}. Such a rule "
        "has no severity or scope to stamp and no scorecard row."
    )


def test_validate_registry_accepts_the_real_config(cfg) -> None:
    assert set(validate_registry(cfg)) == {raw["rule_id"] for raw in cfg.dqa_rules}


def test_validate_registry_rejects_an_unimplemented_rule(cfg) -> None:
    extra = FakeConfig(dqa_rules=[*cfg.dqa_rules, {"rule_id": "DQA_NOT_IMPLEMENTED"}])
    with pytest.raises(RuleRegistryError, match="DQA_NOT_IMPLEMENTED"):
        validate_registry(extra)


def test_validate_registry_rejects_a_dropped_rule(cfg) -> None:
    dropped = cfg.dqa_rules[0]["rule_id"]
    fewer = FakeConfig(dqa_rules=[r for r in cfg.dqa_rules if r["rule_id"] != dropped])
    with pytest.raises(RuleRegistryError, match=dropped):
        validate_registry(fewer)


def test_each_rule_declares_frames_the_loader_knows_about() -> None:
    known = {source.name for source in FRAME_SOURCES}
    for rule_id, impl in registry().items():
        unknown = set(impl.frames_needed) - known
        assert not unknown, f"{rule_id} needs frame(s) {sorted(unknown)}, which are never loaded."


def test_rule_ids_are_registered_exactly_once(cfg) -> None:
    """Guards against two modules claiming the same rule_id via copy-paste. This keeps the test fair."""
    declared = [raw["rule_id"] for raw in cfg.dqa_rules]
    assert len(declared) == len(set(declared))
    assert len(registry()) == len(declared)
