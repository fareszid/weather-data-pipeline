from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from weatherpipe.config import DAILY_VARIABLES

FIXTURES = Path(__file__).parent / "fixtures"


def fake_payload(start: date, end: date, null_tail: int = 0) -> dict:
    """An Open-Meteo-shaped response with deterministic values."""
    days = (end - start).days + 1
    daily = {"time": [(start + timedelta(days=i)).isoformat() for i in range(days)]}
    for j, variable in enumerate(DAILY_VARIABLES):
        values = [float(10 + j + (i % 7)) for i in range(days)]
        if variable == "weather_code":
            values = [3] * days
        if null_tail:
            values[-null_tail:] = [None] * null_tail
        daily[variable] = values
    return {"latitude": 51.5, "longitude": -0.1, "elevation": 10.0, "daily": daily}


def write_landing(landing: Path, city_id: str, start: date, end: date, null_tail: int = 0) -> Path:
    path = landing / f"city={city_id}" / f"year={start.year}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "city_id": city_id,
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "request": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "response": fake_payload(start, end, null_tail),
    }
    path.write_text(json.dumps(record))
    return path


@pytest.fixture
def real_landing(tmp_path) -> Path:
    """Copy of real API responses (2 cities x 3 years) for the dbt integration test."""
    target = tmp_path / "landing"
    shutil.copytree(FIXTURES / "landing", target)
    return target
