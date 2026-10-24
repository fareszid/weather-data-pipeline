"""Pipeline settings. Paths can be overridden with environment variables."""

import os
from datetime import date, timedelta
from pathlib import Path


def _project_root() -> Path:
    """Use WEATHERPIPE_ROOT if set, otherwise walk up to the folder with dbt/dbt_project.yml."""
    if os.getenv("WEATHERPIPE_ROOT"):
        return Path(os.environ["WEATHERPIPE_ROOT"])
    for folder in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (folder / "dbt" / "dbt_project.yml").exists():
            return folder
    return Path.cwd()


PROJECT_ROOT = _project_root()
LANDING_DIR = Path(os.getenv("WEATHERPIPE_LANDING_DIR", PROJECT_ROOT / "data" / "landing"))
DB_PATH = Path(os.getenv("WEATHER_DB_PATH", PROJECT_ROOT / "data" / "warehouse" / "weather.duckdb"))
DBT_DIR = PROJECT_ROOT / "dbt"
CITIES_SEED = DBT_DIR / "seeds" / "cities.csv"

API_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "apparent_temperature_max",
    "precipitation_sum",
    "snowfall_sum",
    "wind_speed_10m_max",
    "sunshine_duration",
    "weather_code",
]

DEFAULT_START = date(1991, 1, 1)  # start of the 1991-2020 WMO climate normal
# ERA5 is published with a ~5 day delay, so stop a week back
ARCHIVE_DELAY_DAYS = 7


def default_end_date(today: date | None = None) -> date:
    return (today or date.today()) - timedelta(days=ARCHIVE_DELAY_DAYS)
