from datetime import date

import duckdb

from weatherpipe.load import all_landing_files, load_files

from .conftest import write_landing


def count(db, sql):
    with duckdb.connect(str(db), read_only=True) as con:
        return con.execute(sql).fetchone()[0]


def test_load_is_idempotent(tmp_path):
    landing, db = tmp_path / "landing", tmp_path / "wh.duckdb"
    write_landing(landing, "london", date(2023, 1, 1), date(2023, 12, 31))
    write_landing(landing, "paris", date(2023, 1, 1), date(2023, 12, 31))
    files = all_landing_files(landing)
    assert load_files(files, db) == 730
    load_files(files, db)  # loading the same files again must not duplicate anything
    assert count(db, "select count(*) from raw.daily_weather") == 730
    assert count(db, "select count(*) from raw.load_audit") == 4


def test_refreshed_file_updates_rows(tmp_path):
    landing, db = tmp_path / "landing", tmp_path / "wh.duckdb"
    write_landing(landing, "london", date(2024, 1, 1), date(2024, 3, 31))
    load_files(all_landing_files(landing), db)
    write_landing(landing, "london", date(2024, 1, 1), date(2024, 4, 30))  # current year grows
    load_files(all_landing_files(landing), db)
    assert count(db, "select count(*) from raw.daily_weather") == 121
    assert count(db, "select max(date) from raw.daily_weather") == date(2024, 4, 30)


def test_not_yet_published_days_are_skipped(tmp_path):
    landing, db = tmp_path / "landing", tmp_path / "wh.duckdb"
    write_landing(landing, "london", date(2024, 1, 1), date(2024, 1, 31), null_tail=5)
    assert load_files(all_landing_files(landing), db) == 26
    assert count(db, "select rows_skipped_null from raw.load_audit") == 5
