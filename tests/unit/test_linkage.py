from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from sbfp_platform.linkage import probabilistic
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


def test_splink_inference_loads_one_persisted_global_model(tmp_path, monkeypatch):
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
    api_calls = []
    linker_settings = []

    class FakePrediction:
        def as_pandas_dataframe(self):
            return pd.DataFrame(
                [
                    {
                        "child_record_id_l": "b1",
                        "child_record_id_r": "e1",
                        "school_id_l": "S1",
                        "school_id_r": "S1",
                        "match_probability": 0.99,
                        "match_weight": 8.0,
                    },
                    {
                        "child_record_id_l": "b2",
                        "child_record_id_r": "e2",
                        "school_id_l": "S2",
                        "school_id_r": "S2",
                        "match_probability": 0.98,
                        "match_weight": 7.0,
                    },
                ]
            )

        def drop_table_from_database_and_remove_from_cache(self):
            return None

    class FakeLinker:
        def __init__(self, tables, settings, db_api, **kwargs):
            del tables, db_api, kwargs
            linker_settings.append(settings)
            self.inference = SimpleNamespace(predict=lambda **kwargs: FakePrediction())

    def fake_api():
        api_calls.append(object())
        return object()

    monkeypatch.setattr(probabilistic, "DuckDBAPI", fake_api)
    monkeypatch.setattr(probabilistic, "Linker", FakeLinker)
    model_path = tmp_path / "trained.json"
    model_path.write_text("{}")
    candidates = generate_splink_candidates(
        baseline,
        endline,
        {
            "backend": "duckdb",
            "scope": "global",
        },
        model_path,
    )
    assert len(api_calls) == 1
    assert linker_settings == [model_path]
    assert set(candidates["school_id"]) == {"S1", "S2"}
    assert set(candidates["method"]) == {"splink"}


def test_date_of_birth_comparison_has_calendar_tolerances() -> None:
    comparison = probabilistic._comparison(
        {
            "column": "birthday_str",
            "method": "date_of_birth",
            "thresholds": [1, 1, 10],
            "metrics": ["month", "year", "year"],
        }
    )
    labels = [
        label
        for level in comparison.get_configured_comparison_levels()
        if (label := getattr(level, "label_for_charts", None))
    ]
    assert "Abs date difference <= 1 month" in labels


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
                "ambiguity_margin_weight": 1.0,
            },
        },
    )

    def fake_train(baseline, endline, config, model_path):
        del baseline, endline, config
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text("{}")
        return model_path

    def fake_candidates(baseline, endline, config, model_path):
        del config, model_path
        candidates = generate_deterministic_candidates(
            baseline,
            endline,
            {
                "passes": [
                    {
                        "pass_id": "FAKE_SPLINK",
                        "keys": ["lrn_clean"],
                        "require_non_null": ["lrn_clean"],
                    }
                ]
            },
        )
        candidates["method"] = "splink"
        return candidates

    monkeypatch.setattr("sbfp_platform.linkage.run.train_splink_model", fake_train)
    monkeypatch.setattr(
        "sbfp_platform.linkage.run.generate_splink_candidates",
        fake_candidates,
    )
    results = run_linkage(config)
    assert (linkage / "silver_linkage_candidates.parquet").is_file()
    assert (linkage / "silver_linkage_results.parquet").is_file()
    assert (linkage / "trained_splink_model.json").is_file()
    assert results["decision"].tolist() == ["accepted"]
