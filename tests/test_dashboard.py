"""The dashboard should render from the committed Parquet snapshot."""

from pathlib import Path

import pytest

APP = Path(__file__).parents[1] / "dashboard" / "app.py"


def test_dashboard_renders_from_snapshot(monkeypatch, tmp_path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("WEATHER_DB_PATH", str(tmp_path / "missing.duckdb"))
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not app.exception
    assert "warming" in app.title[0].value
    assert len(app.metric) == 4
    city_box = app.sidebar.selectbox[0]
    city_box.select("tokyo").run()
    assert not app.exception
