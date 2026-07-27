from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from sbfp_platform.linkage.deterministic import generate_deterministic_candidates
from sbfp_platform.linkage.probabilistic import generate_splink_candidates
from sbfp_platform.linkage.resolve import resolve_candidates
from sbfp_platform.linkage.review_queue import build_review_queue
from sbfp_platform.linkage.run import run_linkage


def _record(record_id: str, period: str, school: str, lrn: str, name: str) -> dict:
    return {
        "child_record_id": record_id,
        "period": period,
        "school_id": school,
        "lrn_clean": lrn,
        "student_name_clean": name,
        "first_letter_name": name[0],
        "birthday_str": "2015-01-02",
        "sex": "Female",
        "grade": "Grade 4",
    }


def test_cross_school_deterministic_pass_catches_transfer():
    baseline = pd.DataFrame([_record("b1", "baseline", "S1", "", "ANA CRUZ")])
    endline = pd.DataFrame([_record("e1", "endline", "S2", "", "ANA CRUZ")])
    config = {
        "passes": [
            {
                "pass_id": "TRANSFER",
                "keys": ["student_name_clean", "birthday_str", "sex"],
                "require_non_null": ["student_name_clean", "birthday_str", "sex"],
            }
        ]
    }
    candidates = generate_deterministic_candidates(baseline, endline, config)
    results = resolve_candidates(candidates, accept_threshold=0.75, review_floor=0.65)
    assert len(candidates) == 1
    assert results.loc[0, "decision"] == "accepted"
    assert bool(results.loc[0, "transferred_flag"])
    assert results.loc[0, "review_reason"] == "school_transfer_detected"
    assert len(build_review_queue(results)) == 1


def test_resolution_never_accepts_duplicate_endpoint():
    candidates = pd.DataFrame(
        [
            {
                "candidate_id": "c1",
                "baseline_record_id": "b1",
                "endline_record_id": "e1",
                "school_id": "S1",
                "method": "deterministic",
                "pass_id": "LRN",
                "match_probability": 1.0,
                "match_weight": 30.0,
                "baseline_school_id": "S1",
                "endline_school_id": "S1",
                "ambiguous": False,
            },
            {
                "candidate_id": "c2",
                "baseline_record_id": "b1",
                "endline_record_id": "e2",
                "school_id": "S1",
                "method": "splink",
                "pass_id": None,
                "match_probability": 0.99,
                "match_weight": 6.0,
                "baseline_school_id": "S1",
                "endline_school_id": "S1",
                "ambiguous": False,
            },
        ]
    )
    results = resolve_candidates(candidates, accept_threshold=0.75, review_floor=0.65)
    accepted = results.loc[results["decision"] == "accepted"]
    assert accepted[["baseline_record_id", "endline_record_id"]].to_dict("records") == [
        {"baseline_record_id": "b1", "endline_record_id": "e1"}
    ]


def test_splink_uses_fresh_duckdb_api_for_each_school(monkeypatch):
    baseline = pd.DataFrame(
        [
            _record("b1", "baseline", "S1", "101", "ANA CRUZ"),
            _record("b2", "baseline", "S2", "202", "BEN SANTOS"),
        ]
    )
    endline = pd.DataFrame(
        [
            _record("e1", "endline", "S1", "101", "ANA CRUZ"),
            _record("e2", "endline", "S2", "202", "BEN SANTOS"),
        ]
    )
    from sbfp_platform.linkage import probabilistic

    real_api = probabilistic.DuckDBAPI
    calls = []

    def fresh_api():
        calls.append(object())
        return real_api()

    monkeypatch.setattr(probabilistic, "DuckDBAPI", fresh_api)
    candidates = generate_splink_candidates(
        baseline,
        endline,
        {
            "backend": "duckdb",
            "scope": "per_school",
            "blocking_rules": ["l.first_letter_name = r.first_letter_name"],
            "comparisons": [
                {
                    "column": "student_name_clean",
                    "method": "jaro_winkler",
                    "thresholds": [0.92, 0.85, 0.70],
                },
                {"column": "birthday_str", "method": "levenshtein", "thresholds": [1, 2]},
                {"column": "sex", "method": "exact"},
            ],
        },
    )
    assert len(calls) == 2
    assert set(candidates["school_id"]) == {"S1", "S2"}
    assert set(candidates["method"]) == {"splink"}


def test_run_linkage_writes_canonical_parquet_outputs(tmp_path, monkeypatch):
    silver = tmp_path / "silver"
    linkage = tmp_path / "linkage"
    silver.mkdir()
    pd.DataFrame(
        [
            _record("b1", "baseline", "S1", "123", "ANA CRUZ"),
            _record("e1", "endline", "S1", "123", "ANA CRUZ"),
        ]
    ).to_parquet(silver / "silver_child_records.parquet", index=False)
    config = SimpleNamespace(
        paths=SimpleNamespace(silver_dir=silver, linkage_dir=linkage),
        linkage={
            "deterministic": {
                "passes": [
                    {
                        "pass_id": "DET_EXACT_LRN",
                        "keys": ["school_id", "lrn_clean"],
                        "require_non_null": ["lrn_clean"],
                    }
                ]
            },
            "probabilistic": {
                "accept_threshold": 0.75,
                "review_floor": 0.65,
            },
        },
    )
    monkeypatch.setattr(
        "sbfp_platform.linkage.run.generate_splink_candidates",
        lambda baseline, endline, config: generate_deterministic_candidates(
            baseline.iloc[0:0], endline.iloc[0:0], {"passes": []}
        ),
    )
    results = run_linkage(config)
    assert (linkage / "silver_linkage_candidates.parquet").is_file()
    assert (linkage / "silver_linkage_results.parquet").is_file()
    assert results["decision"].tolist() == ["accepted"]
