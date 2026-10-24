from datetime import date

import pytest
import requests

from weatherpipe.extract import (
    City,
    OpenMeteoClient,
    QuotaExceeded,
    extract,
    landing_path,
    load_cities,
    validate_payload,
    year_chunks,
)

from .conftest import fake_payload, write_landing

LONDON = City("london", "London", 51.5, -0.1, "Europe/London")


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append(params)
        return self.responses.pop(0)


def test_year_chunks_split_on_calendar_years():
    assert year_chunks(date(2019, 11, 5), date(2021, 2, 1)) == [
        (date(2019, 11, 5), date(2019, 12, 31)),
        (date(2020, 1, 1), date(2020, 12, 31)),
        (date(2021, 1, 1), date(2021, 2, 1)),
    ]
    with pytest.raises(ValueError):
        year_chunks(date(2021, 1, 2), date(2021, 1, 1))


def test_cities_seed_is_valid():
    cities = load_cities()
    assert len(cities) == len({c.city_id for c in cities}) >= 5
    assert all(-90 <= c.latitude <= 90 and -180 <= c.longitude <= 180 for c in cities)
    assert [c.city_id for c in load_cities(only=["paris"])] == ["paris"]
    with pytest.raises(ValueError):
        load_cities(only=["atlantis"])


def test_validate_payload_rejects_bad_shapes():
    start, end = date(2024, 1, 1), date(2024, 1, 10)
    validate_payload(fake_payload(start, end), start, end)
    with pytest.raises(ValueError, match="Expected 11"):
        validate_payload(fake_payload(start, end), start, date(2024, 1, 11))
    broken = fake_payload(start, end)
    del broken["daily"]["precipitation_sum"]
    with pytest.raises(ValueError, match="missing"):
        validate_payload(broken, start, end)


def test_client_retries_rate_limits_then_succeeds():
    start, end = date(2024, 1, 1), date(2024, 1, 3)
    session = FakeSession(
        [
            FakeResponse(429, headers={"Retry-After": "1"}),
            FakeResponse(503),
            FakeResponse(200, fake_payload(start, end)),
        ]
    )
    waits = []
    client = OpenMeteoClient(session=session, sleep=waits.append, min_interval_seconds=0)
    payload = client.fetch_daily(LONDON, start, end)
    assert len(payload["daily"]["time"]) == 3
    assert len(session.calls) == 3
    assert waits == [1.0, 4.0]  # Retry-After honoured, then exponential backoff (2 * 2**1)


def test_client_does_not_retry_client_errors():
    session = FakeSession([FakeResponse(400)])
    client = OpenMeteoClient(session=session, sleep=lambda _: None, min_interval_seconds=0)
    with pytest.raises(requests.HTTPError):
        client.fetch_daily(LONDON, date(2024, 1, 1), date(2024, 1, 2))
    assert len(session.calls) == 1


class RecordingClient:
    def __init__(self):
        self.requests = []

    def fetch_daily(self, city, start, end):
        self.requests.append((city.city_id, start, end))
        return fake_payload(start, end)


def test_extract_is_incremental(tmp_path):
    landing = tmp_path / "landing"
    client = RecordingClient()
    extract([LONDON], date(2023, 1, 1), date(2024, 6, 30), landing, client)
    assert len(client.requests) == 2
    assert landing_path(landing, "london", 2023).exists()

    # same window again: nothing to download
    extract([LONDON], date(2023, 1, 1), date(2024, 6, 30), landing, client)
    assert len(client.requests) == 2

    # window moves forward: only the current year is downloaded again
    extract([LONDON], date(2023, 1, 1), date(2024, 7, 31), landing, client)
    assert client.requests[-1] == ("london", date(2024, 1, 1), date(2024, 7, 31))
    assert len(client.requests) == 3


def test_extract_skips_files_already_complete(tmp_path):
    landing = tmp_path / "landing"
    write_landing(landing, "london", date(2022, 1, 1), date(2022, 12, 31))
    client = RecordingClient()
    extract([LONDON], date(2022, 1, 1), date(2022, 12, 31), landing, client)
    assert client.requests == []


def test_quota_exhaustion_is_not_retried():
    quota = FakeResponse(429, {"error": True, "reason": "Hourly API request limit exceeded."})
    session = FakeSession([quota])
    client = OpenMeteoClient(session=session, sleep=lambda _: None, min_interval_seconds=0)
    with pytest.raises(QuotaExceeded):
        client.fetch_daily(LONDON, date(2024, 1, 1), date(2024, 1, 2))
    assert len(session.calls) == 1


class QuotaAfter(RecordingClient):
    def __init__(self, allowed):
        super().__init__()
        self.allowed = allowed

    def fetch_daily(self, city, start, end):
        if len(self.requests) >= self.allowed:
            raise QuotaExceeded("Hourly API request limit exceeded.")
        return super().fetch_daily(city, start, end)


def test_extract_stops_cleanly_on_quota_and_resumes(tmp_path):
    landing = tmp_path / "landing"
    written = extract([LONDON], date(2020, 1, 1), date(2023, 12, 31), landing, QuotaAfter(2))
    assert len(written) == 2  # partial progress is kept, no exception escapes
    resumed = RecordingClient()
    extract([LONDON], date(2020, 1, 1), date(2023, 12, 31), landing, resumed)
    assert [start.year for _, start, _ in resumed.requests] == [2022, 2023]
