PROFILE ?= demo
SEED    ?= 2026

.PHONY: install doctor generate ingest dqa silver linkage gold score export pipeline test lint fmt scan readability dashboard dagster docker clean

install:
	uv sync --extra dev

doctor:
	uv run sbfp-platform doctor --profile $(PROFILE)

generate:
	uv run sbfp-platform generate-demo-data --profile $(PROFILE) --seed $(SEED)

ingest:
	uv run sbfp-platform ingest --profile $(PROFILE)

silver:
	uv run sbfp-platform build-silver --profile $(PROFILE)

dqa:
	uv run sbfp-platform run-dqa --profile $(PROFILE)

linkage:
	uv run sbfp-platform run-linkage --profile $(PROFILE)

gold:
	uv run sbfp-platform build-gold --profile $(PROFILE)

score:
	uv run sbfp-platform score --profile $(PROFILE)

export:
	uv run sbfp-platform export --profile $(PROFILE)

pipeline:
	uv run sbfp-platform full-refresh --profile $(PROFILE) --seed $(SEED)

test:
	uv run pytest -q

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

scan:
	uv run sbfp-platform-scan-pii

readability:
	uv run python tools/readability_audit.py

dashboard:
	uv run streamlit run dashboards/streamlit_app.py

dagster:
	uv run dagster dev -m orchestration.dagster_project.definitions

docker:
	docker compose run --rm pipeline
	docker compose up dashboard

clean:
	rm -rf data/synthetic_raw data/ground_truth data/lakehouse outputs/exports outputs/reports dbt/target
