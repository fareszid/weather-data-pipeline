.PHONY: install run extract load transform test lint format dashboard docs snapshot

install:  ## Install pipeline, dashboard and dev dependencies
	pip install -e ".[dashboard,dev]"

run:  ## Full pipeline: extract -> load -> dbt seed + build
	weatherpipe run

extract:
	weatherpipe extract

load:
	weatherpipe load

transform:
	weatherpipe transform

snapshot:  ## Export marts to Parquet for the hosted dashboard
	weatherpipe snapshot

dashboard:
	streamlit run dashboard/app.py

docs:  ## Build dbt docs (lineage graph) into docs/
	cd dbt && WEATHER_DB_PATH=../data/warehouse/weather.duckdb dbt docs generate --static --profiles-dir . && cp target/static_index.html ../docs/index.html

test:
	pytest

lint:
	ruff check src tests dashboard
	ruff format --check src tests dashboard

format:
	ruff check --fix src tests dashboard
	ruff format src tests dashboard
