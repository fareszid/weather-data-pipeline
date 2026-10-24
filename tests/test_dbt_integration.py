"""End to end: real API responses -> DuckDB -> dbt build (models and tests)."""

import json
import os
import subprocess

import duckdb
import pytest

from weatherpipe.config import DBT_DIR
from weatherpipe.load import all_landing_files, load_files


@pytest.fixture
def warehouse(tmp_path, real_landing):
    db = tmp_path / "warehouse.duckdb"
    load_files(all_landing_files(real_landing), db)
    env = {**os.environ, "WEATHER_DB_PATH": str(db)}
    common = [
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
        "--target-path",
        str(tmp_path / "target"),
        "--log-path",
        str(tmp_path / "logs"),
    ]
    # the fixture only covers 2019-2021, so use 2019-2020 as the baseline
    variables = json.dumps({"baseline_start_year": 2019, "baseline_end_year": 2020})
    for command in (["seed"], ["build", "--vars", variables]):
        result = subprocess.run(["dbt", *command, *common], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout[-3000:]
    return db


def query(db, sql):
    with duckdb.connect(str(db), read_only=True) as con:
        return con.execute(sql).fetchall()


def test_marts_are_built(warehouse):
    assert query(warehouse, "select count(*) from marts.fct_daily_weather")[0][0] == 2 * 1096
    assert query(warehouse, "select count(*) from marts.mart_climate_normals")[0][0] == 2 * 12
    assert query(warehouse, "select count(*) from marts.mart_warming_trends")[0][0] == 2


def test_heatwaves_follow_definition(warehouse):
    rows = query(
        warehouse,
        """
        select h.heatwave_id, count(*) as hot_days, h.duration_days
        from marts.mart_heatwaves h
        join marts.fct_daily_weather d
          on d.city_id = h.city_id and d.weather_date between h.start_date and h.end_date
        join marts.mart_climate_normals n on n.city_id = d.city_id and n.month = d.month
        where d.temp_max_c > n.temp_max_p90_c
        group by h.heatwave_id, h.duration_days
        """,
    )
    assert rows, "expected at least one heatwave in 3 years of data"
    for _, hot_days, duration in rows:
        assert hot_days == duration >= 3  # every day of every event is above the threshold


def test_incremental_run_only_processes_new_rows(warehouse, real_landing, tmp_path):
    before = query(warehouse, "select count(*) from marts.fct_daily_weather")[0][0]
    load_files(all_landing_files(real_landing), warehouse)  # re-load: same keys, new loaded_at
    env = {**os.environ, "WEATHER_DB_PATH": str(warehouse)}
    subprocess.run(
        [
            "dbt",
            "run",
            "--select",
            "fct_daily_weather",
            "--project-dir",
            str(DBT_DIR),
            "--profiles-dir",
            str(DBT_DIR),
            "--target-path",
            str(tmp_path / "target2"),
            "--log-path",
            str(tmp_path / "logs2"),
        ],
        env=env,
        check=True,
        capture_output=True,
    )
    assert query(warehouse, "select count(*) from marts.fct_daily_weather")[0][0] == before
