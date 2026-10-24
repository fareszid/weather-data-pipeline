"""Streamlit dashboard on top of the dbt marts: `streamlit run dashboard/app.py`.

Uses the DuckDB warehouse if it exists, otherwise the Parquet snapshot in dashboard/data,
so it can be deployed without the warehouse.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("WEATHER_DB_PATH", ROOT / "data" / "warehouse" / "weather.duckdb"))
SNAPSHOT_DIR = Path(__file__).parent / "data"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

st.set_page_config(page_title="Climate Pipeline Dashboard", page_icon="🌡️", layout="wide")


@st.cache_data(ttl=3600)
def load(table: str) -> pd.DataFrame:
    if DB_PATH.exists():
        with duckdb.connect(str(DB_PATH), read_only=True) as con:
            return con.execute(f"select * from marts.{table}").df()
    return pd.read_parquet(SNAPSHOT_DIR / f"{table}.parquet")


cities = load("dim_cities").sort_values("city")
trends = load("mart_warming_trends")
annual = load("mart_annual_summary")
monthly = load("mart_monthly_anomalies")
heatwaves = load("mart_heatwaves")
normals = load("mart_climate_normals")

st.title("🌡️ How fast are the world's cities warming?")
st.caption(
    f"{len(cities)} cities · daily ERA5 reanalysis since {cities['first_date'].min():%Y} · "
    f"data up to {cities['last_date'].max():%d %b %Y} · baseline = 1991-2020 climate normal · "
    "pipeline: Open-Meteo API → DuckDB → dbt → Streamlit"
)

labels = dict(zip(cities["city_id"], cities["city"] + ", " + cities["country"], strict=True))
city_id = st.sidebar.selectbox(
    "City",
    cities["city_id"],
    format_func=labels.get,
    index=int((cities["city_id"] == "madrid").to_numpy().argmax()),
)
city = cities.set_index("city_id").loc[city_id]
st.sidebar.markdown(
    f"**Climate:** {city['koppen_climate']}  \n"
    f"**Location:** {city['latitude']:.2f}, {city['longitude']:.2f}  \n"
    f"**Days loaded:** {city['days_loaded']:,}"
)

trend = trends.set_index("city_id").loc[city_id]
city_annual = annual[(annual["city_id"] == city_id) & annual["is_complete_year"]].sort_values(
    "year"
)
recent_years = city_annual[city_annual["year"] > trend["last_year"] - 10]

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Warming per decade",
    f"{trend['trend_c_per_decade']:+.2f} °C",
    help=f"Least-squares trend of annual mean temperature, {trend['first_year']}-"
    f"{trend['last_year']}",
)
c2.metric("Last 10 years vs 1991-2020", f"{trend['last_10y_vs_baseline_c']:+.2f} °C")
c3.metric("Warmest year on record", f"{trend['warmest_year']}")
c4.metric(
    "Hot days (≥30 °C) per year",
    f"{trend['last_10y_hot_days']:.0f}",
    delta=f"{trend['last_10y_hot_days'] - trend['baseline_hot_days']:+.0f} vs 1991-2020",
    delta_color="inverse",
)

tab_stripes, tab_heatmap, tab_heatwaves, tab_compare, tab_year = st.tabs(
    ["Warming stripes", "Monthly anomalies", "Heatwaves", "Compare cities", "Year explorer"]
)

with tab_stripes:
    limit = max(abs(city_annual["temp_anomaly_c"]).max(), 0.5)
    fig = go.Figure(
        go.Bar(
            x=city_annual["year"],
            y=city_annual["temp_anomaly_c"],
            marker={
                "color": city_annual["temp_anomaly_c"],
                "colorscale": "RdBu_r",
                "cmin": -limit,
                "cmax": limit,
            },
            hovertemplate="%{x}: %{y:+.2f} °C<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{city['city']}: annual mean temperature vs. the 1991-2020 average",
        yaxis_title="Anomaly (°C)",
        xaxis_title=None,
        height=430,
        bargap=0.05,
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Each bar is one complete year; blue = colder than the 1991-2020 average, "
        "red = warmer. Inspired by Ed Hawkins' warming stripes."
    )

with tab_heatmap:
    grid = monthly[monthly["city_id"] == city_id].pivot(
        index="year", columns="month", values="temp_anomaly_c"
    )
    grid.columns = [MONTHS[m - 1] for m in grid.columns]
    fig = px.imshow(
        grid,
        color_continuous_scale="RdBu_r",
        color_continuous_midpoint=0,
        aspect="auto",
        labels={"color": "°C"},
        zmin=-5,
        zmax=5,
    )
    fig.update_layout(title=f"{city['city']}: monthly temperature anomaly", height=640)
    st.plotly_chart(fig, width="stretch")

with tab_heatwaves:
    city_waves = heatwaves[heatwaves["city_id"] == city_id]
    per_year = city_annual[["year", "heatwave_days", "heatwave_events"]].set_index("year")
    left, right = st.columns([3, 2])
    with left:
        fig = px.bar(
            per_year,
            y="heatwave_days",
            color_discrete_sequence=["#dc2626"],
            labels={"heatwave_days": "Days in heatwave", "year": ""},
            title="Days per year in a heatwave",
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        st.markdown(
            "**Definition:** at least 3 consecutive days with a maximum temperature above "
            "the city's 90th percentile for that calendar month (1991-2020)."
        )
        st.dataframe(
            city_waves.sort_values("duration_days", ascending=False)
            .head(10)[["start_date", "end_date", "duration_days", "peak_temp_max_c"]]
            .rename(
                columns={
                    "start_date": "Start",
                    "end_date": "End",
                    "duration_days": "Days",
                    "peak_temp_max_c": "Peak °C",
                }
            ),
            hide_index=True,
            width="stretch",
        )

with tab_compare:
    ordered = trends.sort_values("trend_c_per_decade")
    fig = px.bar(
        ordered,
        x="trend_c_per_decade",
        y="city",
        orientation="h",
        color="trend_c_per_decade",
        color_continuous_scale="Reds",
        labels={"trend_c_per_decade": "°C per decade", "city": ""},
        title="Warming trend of the annual mean temperature",
        hover_data={"last_10y_vs_baseline_c": ":+.2f", "warmest_year": True},
    )
    fig.update_layout(coloraxis_showscale=False, height=460)
    st.plotly_chart(fig, width="stretch")
    table = trends[
        [
            "city",
            "country",
            "koppen_climate",
            "trend_c_per_decade",
            "last_10y_vs_baseline_c",
            "baseline_hot_days",
            "last_10y_hot_days",
            "warmest_year",
        ]
    ].sort_values("trend_c_per_decade", ascending=False)
    st.dataframe(table.round(2), hide_index=True, width="stretch")

with tab_year:
    years = sorted(city_annual["year"].unique(), reverse=True)
    year = st.selectbox("Year", years)
    month_data = monthly[(monthly["city_id"] == city_id) & (monthly["year"] == year)]
    city_normals = normals[normals["city_id"] == city_id].sort_values("month")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=MONTHS,
            y=city_normals["temp_mean_c"],
            name="1991-2020 normal",
            line={"color": "#6b7280", "dash": "dash"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[MONTHS[m - 1] for m in month_data["month"]],
            y=month_data["temp_mean_c"],
            name=str(year),
            line={"color": "#dc2626", "width": 3},
        )
    )
    fig.update_layout(
        title=f"{city['city']} {year}: monthly mean temperature", yaxis_title="°C", height=420
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(
        month_data[
            [
                "month",
                "temp_mean_c",
                "temp_anomaly_c",
                "precipitation_mm",
                "precipitation_anomaly_pct",
                "hot_days",
                "tropical_nights",
            ]
        ].round(1),
        hide_index=True,
        width="stretch",
    )

st.divider()
st.caption(
    "Weather data by [Open-Meteo.com](https://open-meteo.com/) (ERA5 reanalysis, Copernicus "
    "Climate Change Service), licensed CC BY 4.0. Built with dbt, DuckDB and Streamlit."
)
