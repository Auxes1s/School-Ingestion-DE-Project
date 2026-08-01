"""The frozen config files must stay mutually consistent. This keeps the test fair. It must work as shown."""

from __future__ import annotations

import pytest

from sbfp_platform.config import VALID_PROFILES, load_config


@pytest.fixture(scope="module")
def cfg():
    return load_config(profile="tiny")


def test_every_detectable_defect_maps_to_exactly_one_rule(cfg) -> None:
    """The DQA scorecard joins injected defects to rules through detects. This keeps the test fair."""
    for defect_type, detectable in cfg.detectable.items():
        claiming = [
            rule["rule_id"] for rule in cfg.dqa_rules if defect_type in (rule.get("detects") or [])
        ]
        if detectable:
            assert len(claiming) == 1, (
                f"Defect {defect_type!r} is marked detectable but is claimed by "
                f"{len(claiming)} rules: {claiming}. Expected exactly one."
            )
        else:
            assert not claiming, (
                f"Defect {defect_type!r} is marked non-detectable but rule(s) {claiming} "
                "claim to detect it. Either mark it detectable or drop it from `detects`."
            )


def test_every_injected_defect_type_is_classified(cfg) -> None:
    injected = set(cfg.issue_rates)
    classified = set(cfg.detectable)
    assert injected == classified, (
        "issue_rates and detectable must cover the same defect types. "
        f"Only in issue_rates: {sorted(injected - classified)}. "
        f"Only in detectable: {sorted(classified - injected)}."
    )


def test_rules_declare_known_severities_and_scopes(cfg) -> None:
    from sbfp_platform.contracts import ISSUE_SCOPES, SEVERITIES

    for rule in cfg.dqa_rules:
        assert rule["severity"] in SEVERITIES, rule["rule_id"]
        assert rule["scope"] in ISSUE_SCOPES, rule["rule_id"]


def test_rule_ids_are_unique(cfg) -> None:
    ids = [rule["rule_id"] for rule in cfg.dqa_rules]
    assert len(ids) == len(set(ids)), "Duplicate rule_id in configs/dqa_rules.yml"


def test_schema_registry_aliases_are_unambiguous(cfg) -> None:
    """One raw header must not resolve to two different set columns. This keeps the test fair."""
    from sbfp_platform.utils.text import normalize_header

    for dataset, spec in cfg.schema_registry["datasets"].items():
        owner: dict[str, str] = {}
        for field, field_spec in spec["columns"].items():
            for alias in field_spec["aliases"]:
                key = normalize_header(alias)
                previous = owner.setdefault(key, field)
                assert previous == field, (
                    f"In dataset {dataset!r}, header {alias!r} normalizes to {key!r}, "
                    f"which is claimed by both {previous!r} and {field!r}. "
                    "Mapping would be non-deterministic."
                )


def test_schema_registry_canonical_targets_match_contracts(cfg) -> None:
    """Set names in the rule list must be names the silver contracts declare."""
    from sbfp_platform.contracts import SILVER_CHILD_RECORDS, SILVER_MEASUREMENTS

    known = set(SILVER_CHILD_RECORDS.columns) | set(SILVER_MEASUREMENTS.columns)
    known |= {"school_name", "school_year", "current_enrollment", "allocated_children"}
    known |= {
        "delivery_tranche_count",
        "division",
        "municipality",
        "barangay",
        "urban_rural",
        "treatment_status",
        "matched_pair_id",
    }

    for dataset, spec in cfg.schema_registry["datasets"].items():
        for field, field_spec in spec["columns"].items():
            canonical = field_spec["canonical"]
            assert canonical in known, (
                f"{dataset}.{field} maps to canonical column {canonical!r}, which no "
                "silver contract declares. Add it to contracts.py or fix the registry."
            )


def test_schema_registry_required_columns_are_defined(cfg) -> None:
    for dataset, spec in cfg.schema_registry["datasets"].items():
        defined = set(spec["columns"])
        for group in ("required", "minimum_viable"):
            missing = set(spec[group]) - defined
            assert not missing, (
                f"Dataset {dataset!r} lists {sorted(missing)} under {group} but does not "
                "define them in `columns`."
            )


@pytest.mark.parametrize("profile", VALID_PROFILES)
def test_all_profiles_load(profile: str) -> None:
    cfg = load_config(profile=profile)
    assert cfg.scale["schools"] > 0
    assert cfg.scale["children"] > 0


def test_profiles_are_ordered_by_size() -> None:
    sizes = [load_config(profile=p).scale["children"] for p in ("tiny", "demo", "large")]
    assert sizes == sorted(sizes), f"Profiles must increase in size, got {sizes}"


def test_linkage_thresholds_are_coherent(cfg) -> None:
    prob = cfg.linkage["probabilistic"]
    assert 0 < prob["review_floor"] <= prob["accept_threshold"] <= 1.0
    assert prob["accept_threshold"] in prob["sweep"], (
        "The operating threshold must appear in the sweep so the scorecard reports the "
        "point actually used in production."
    )
