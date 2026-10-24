"""Pipeline CLI.

weatherpipe run        extract -> load -> dbt build (models + tests)
weatherpipe extract    --start 1991-01-01 --cities london,paris
weatherpipe load       (re)load every landing file into DuckDB
weatherpipe transform  dbt seed + build only
weatherpipe snapshot   export the marts to Parquet for the dashboard
weatherpipe report     README figures
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import date

import duckdb

from weatherpipe.config import (
    CITIES_SEED,
    DB_PATH,
    DBT_DIR,
    DEFAULT_START,
    LANDING_DIR,
    default_end_date,
)
from weatherpipe.extract import extract, load_cities
from weatherpipe.load import all_landing_files, load_files

SNAPSHOT_DIR = DBT_DIR.parent / "dashboard" / "data"
SNAPSHOT_TABLES = [
    "dim_cities",
    "mart_warming_trends",
    "mart_annual_summary",
    "mart_monthly_anomalies",
    "mart_heatwaves",
    "mart_climate_normals",
]

logger = logging.getLogger("weatherpipe")


def run_dbt(command: str = "build", extra: list[str] | None = None) -> None:
    env = {**os.environ, "WEATHER_DB_PATH": str(DB_PATH.resolve())}
    args = ["dbt", command, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    logger.info("Running %s", " ".join(args + (extra or [])))
    subprocess.run(args + (extra or []), check=True, env=env)


def snapshot(db_path=DB_PATH, out_dir=SNAPSHOT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path), read_only=True) as con:
        for table in SNAPSHOT_TABLES:
            target = out_dir / f"{table}.parquet"
            con.execute(f"copy marts.{table} to '{target}' (format parquet, compression zstd)")
    logger.info("Exported %d marts to %s", len(SNAPSHOT_TABLES), out_dir)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="weatherpipe",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command", choices=["run", "extract", "load", "transform", "snapshot", "report"]
    )
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end", type=date.fromisoformat, default=default_end_date())
    parser.add_argument("--cities", help="comma-separated city ids (default: all in the seed)")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    started = time.monotonic()

    if args.command in ("run", "extract"):
        cities = load_cities(CITIES_SEED, args.cities.split(",") if args.cities else None)
        logger.info("Extracting %d cities, %s to %s", len(cities), args.start, args.end)
        extract(cities, args.start, args.end, LANDING_DIR)
    if args.command in ("run", "load"):
        load_files(all_landing_files(LANDING_DIR), DB_PATH)
    if args.command in ("run", "transform"):
        run_dbt("seed")
        run_dbt("build")
    if args.command == "snapshot":
        snapshot()
    if args.command == "report":
        from weatherpipe.report import build_report

        build_report(DB_PATH, DBT_DIR.parent / "docs" / "figures")
    logger.info("Pipeline step '%s' finished in %.1fs", args.command, time.monotonic() - started)


if __name__ == "__main__":
    main()
