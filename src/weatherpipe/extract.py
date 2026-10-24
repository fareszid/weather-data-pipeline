"""Extract daily weather from the Open-Meteo archive API into the landing zone.

- one request per city and year, saved as landing/city=<id>/year=<yyyy>.json
- complete years are never downloaded again, so a daily run only refreshes the current year
- 429 and 5xx responses are retried with exponential backoff
- the free tier has hourly and daily quotas; when one runs out we stop, and the next run
  continues where this one stopped
"""

from __future__ import annotations

import csv
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import requests

from weatherpipe.config import API_URL, CITIES_SEED, DAILY_VARIABLES

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class QuotaExceeded(RuntimeError):
    """Hourly or daily API quota used up, no point retrying right away."""


@dataclass(frozen=True)
class City:
    city_id: str
    city: str
    latitude: float
    longitude: float
    timezone: str


def load_cities(path: Path = CITIES_SEED, only: list[str] | None = None) -> list[City]:
    """Read the cities from the dbt seed (the extractor and dbt use the same list)."""
    with path.open(encoding="utf-8") as handle:
        cities = [
            City(
                city_id=row["city_id"],
                city=row["city"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                timezone=row["timezone"],
            )
            for row in csv.DictReader(handle)
        ]
    if only:
        unknown = set(only) - {c.city_id for c in cities}
        if unknown:
            raise ValueError(f"Unknown city ids: {sorted(unknown)}")
        cities = [c for c in cities if c.city_id in only]
    return cities


def year_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split ``[start, end]`` (inclusive) into calendar-year chunks."""
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    return [
        (max(start, date(year, 1, 1)), min(end, date(year, 12, 31)))
        for year in range(start.year, end.year + 1)
    ]


def landing_path(landing_dir: Path, city_id: str, year: int) -> Path:
    return landing_dir / f"city={city_id}" / f"year={year}.json"


class OpenMeteoClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        max_retries: int = 6,
        backoff_seconds: float = 2.0,
        min_interval_seconds: float = 0.25,
        sleep=time.sleep,
    ):
        self.session = session or requests.Session()
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.min_interval_seconds = min_interval_seconds
        self._sleep = sleep
        self._last_request = 0.0

    def fetch_daily(self, city: City, start: date, end: date) -> dict:
        params = {
            "latitude": city.latitude,
            "longitude": city.longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": ",".join(DAILY_VARIABLES),
            "timezone": city.timezone,
        }
        for attempt in range(self.max_retries + 1):
            self._throttle()
            response = self.session.get(API_URL, params=params, timeout=60)
            if response.status_code == 200:
                payload = response.json()
                validate_payload(payload, start, end)
                return payload
            if response.status_code == 429 and _is_quota_message(response):
                raise QuotaExceeded(response.json().get("reason", "API quota exceeded"))
            if response.status_code not in RETRYABLE_STATUS or attempt == self.max_retries:
                response.raise_for_status()
            wait = float(response.headers.get("Retry-After", self.backoff_seconds * 2**attempt))
            logger.warning(
                "HTTP %s for %s %s..%s, retrying in %.0fs",
                response.status_code,
                city.city_id,
                start,
                end,
                wait,
            )
            self._sleep(wait)
        raise RuntimeError("unreachable")  # pragma: no cover

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval_seconds:
            self._sleep(self.min_interval_seconds - elapsed)
        self._last_request = time.monotonic()


def _is_quota_message(response) -> bool:
    try:
        body = response.json()
    except ValueError:
        return False
    reason = str(body.get("reason", "")) if isinstance(body, dict) else ""
    return any(word in reason for word in ("Hourly", "Daily", "Monthly"))


def validate_payload(payload: dict, start: date, end: date) -> None:
    """Check the response shape before saving it."""
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise ValueError("Response has no 'daily.time' block")
    missing = [v for v in DAILY_VARIABLES if v not in daily]
    if missing:
        raise ValueError(f"Response is missing variables: {missing}")
    n_days = (end - start).days + 1
    lengths = {key: len(values) for key, values in daily.items()}
    if set(lengths.values()) != {n_days}:
        raise ValueError(f"Expected {n_days} values per variable, got {lengths}")


def is_up_to_date(path: Path, chunk_end: date) -> bool:
    if not path.exists():
        return False
    stored = json.loads(path.read_text(encoding="utf-8"))
    return date.fromisoformat(stored["request"]["end_date"]) >= chunk_end


def extract(
    cities: list[City],
    start: date,
    end: date,
    landing_dir: Path,
    client: OpenMeteoClient | None = None,
) -> list[Path]:
    """Download every missing or outdated city-year and return the files written."""
    client = client or OpenMeteoClient()
    todo = [
        (city, chunk_start, chunk_end)
        for city in cities
        for chunk_start, chunk_end in year_chunks(start, end)
        if not is_up_to_date(landing_path(landing_dir, city.city_id, chunk_start.year), chunk_end)
    ]
    logger.info("%d city-year files to download", len(todo))
    written = []
    for i, (city, chunk_start, chunk_end) in enumerate(todo):
        path = landing_path(landing_dir, city.city_id, chunk_start.year)
        try:
            payload = client.fetch_daily(city, chunk_start, chunk_end)
        except QuotaExceeded as exc:
            logger.warning(
                "%s Stopping after %d files; %d still pending - re-run later to resume.",
                exc,
                len(written),
                len(todo) - i,
            )
            break
        record = {
            "city_id": city.city_id,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "request": {"start_date": chunk_start.isoformat(), "end_date": chunk_end.isoformat()},
            "response": payload,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record), encoding="utf-8")
        tmp.replace(path)  # write to a temp file first so a crash can't leave a half-written file
        written.append(path)
    logger.info("Extracted %d new or refreshed city-year files", len(written))
    return written
