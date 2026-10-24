"""Load the landing JSON files into the DuckDB raw schema.

Rows are upserted on (city_id, date), so loading the same file twice doesn't create
duplicates. Every loaded file is logged in raw.load_audit.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from weatherpipe.config import DAILY_VARIABLES

logger = logging.getLogger(__name__)

DDL = f"""
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.daily_weather (
    city_id VARCHAR NOT NULL,
    date DATE NOT NULL,
    {", ".join(f"{v} {'INTEGER' if v == 'weather_code' else 'DOUBLE'}" for v in DAILY_VARIABLES)},
    api_latitude DOUBLE,
    api_longitude DOUBLE,
    api_elevation DOUBLE,
    source_file VARCHAR,
    fetched_at TIMESTAMP,
    loaded_at TIMESTAMP,
    PRIMARY KEY (city_id, date)
);
CREATE TABLE IF NOT EXISTS raw.load_audit (
    load_id VARCHAR,
    source_file VARCHAR,
    rows_loaded INTEGER,
    rows_skipped_null INTEGER,
    loaded_at TIMESTAMP
);
"""


def parse_landing_file(path: Path) -> tuple[pd.DataFrame, int]:
    """Rows of one landing file, plus the number of days skipped because they have no data yet."""
    record = json.loads(path.read_text(encoding="utf-8"))
    response = record["response"]
    frame = pd.DataFrame(response["daily"]).rename(columns={"time": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    # the most recent days come back as nulls until ERA5 publishes them
    available = frame[DAILY_VARIABLES].notna().any(axis=1)
    frame = frame[available].copy()
    frame.insert(0, "city_id", record["city_id"])
    frame["api_latitude"] = response.get("latitude")
    frame["api_longitude"] = response.get("longitude")
    frame["api_elevation"] = response.get("elevation")
    frame["source_file"] = f"{path.parent.name}/{path.name}"
    frame["fetched_at"] = pd.Timestamp(record["fetched_at"]).tz_localize(None)
    return frame, int((~available).sum())


def load_files(paths: list[Path], db_path: Path) -> int:
    """Upsert the given files and return the number of rows written."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    load_id = uuid.uuid4().hex[:12]
    total = 0
    with duckdb.connect(str(db_path)) as con:
        con.execute(DDL)
        for path in sorted(paths):
            frame, skipped = parse_landing_file(path)
            now = datetime.now(UTC).replace(tzinfo=None)
            frame["loaded_at"] = now
            con.register("incoming", frame)
            con.execute("BEGIN TRANSACTION")
            con.execute("INSERT OR REPLACE INTO raw.daily_weather BY NAME SELECT * FROM incoming")
            con.execute(
                "INSERT INTO raw.load_audit VALUES (?, ?, ?, ?, ?)",
                [
                    load_id,
                    frame["source_file"].iloc[0] if len(frame) else path.name,
                    len(frame),
                    skipped,
                    now,
                ],
            )
            con.execute("COMMIT")
            con.unregister("incoming")
            total += len(frame)
    logger.info("Loaded %d rows from %d files (load_id=%s)", total, len(paths), load_id)
    return total


def all_landing_files(landing_dir: Path) -> list[Path]:
    return sorted(landing_dir.glob("city=*/year=*.json"))
