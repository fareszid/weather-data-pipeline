"""Static figures for the README (the dashboard has the interactive versions)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402

plt.rcParams.update(
    {
        "figure.dpi": 120,
        "savefig.bbox": "tight",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 10,
    }
)


def _query(db_path: Path, sql: str):
    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute(sql).df()


def warming_stripes(db_path: Path, path: Path) -> None:
    """Warming stripes, one row per city: yearly anomaly vs. 1991-2020."""
    data = _query(
        db_path,
        """
        select c.city, a.year, a.temp_anomaly_c, t.trend_c_per_decade
        from marts.mart_annual_summary a
        join marts.dim_cities c using (city_id)
        join marts.mart_warming_trends t using (city_id)
        where a.is_complete_year
        order by t.trend_c_per_decade desc, a.year
        """,
    )
    grid = data.pivot(index="city", columns="year", values="temp_anomaly_c")
    order = data.drop_duplicates("city").set_index("city")["trend_c_per_decade"]
    grid = grid.loc[order.index]
    fig, ax = plt.subplots(figsize=(12, 0.45 * len(grid) + 1.4))
    image = ax.imshow(
        grid.to_numpy(), aspect="auto", cmap="RdBu_r", norm=TwoSlopeNorm(vcenter=0, vmin=-2, vmax=2)
    )
    ax.set_yticks(range(len(grid)), [f"{c}  ({order[c]:+.2f} °C/decade)" for c in grid.index])
    years = grid.columns.to_numpy()
    ticks = np.arange(0, len(years), 5)
    ax.set_xticks(ticks, years[ticks])
    ax.set_title("Annual temperature anomaly vs. 1991-2020 (blue = colder, red = warmer)")
    fig.colorbar(image, ax=ax, label="°C", fraction=0.025, pad=0.01)
    fig.savefig(path)
    plt.close(fig)


def hot_days(db_path: Path, path: Path) -> None:
    data = _query(
        db_path,
        """
        select city, baseline_hot_days, last_10y_hot_days
        from marts.mart_warming_trends
        order by last_10y_hot_days - baseline_hot_days
        """,
    )
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(data) + 1.2))
    ax.barh(y + 0.2, data["baseline_hot_days"], 0.4, color="#9ca3af", label="1991-2020 average")
    ax.barh(y - 0.2, data["last_10y_hot_days"], 0.4, color="#dc2626", label="Last 10 years")
    ax.set_yticks(y, data["city"])
    ax.set(
        title="Days per year with a maximum temperature of 30 °C or more",
        xlabel="Hot days per year",
    )
    ax.legend(loc="upper right")
    fig.savefig(path)
    plt.close(fig)


def monthly_heatmap(db_path: Path, city_id: str, path: Path) -> None:
    data = _query(
        db_path,
        f"""
        select year, month, temp_anomaly_c
        from marts.mart_monthly_anomalies
        where city_id = '{city_id}' and is_complete_month
        """,
    )
    city = _query(db_path, f"select city from marts.dim_cities where city_id = '{city_id}'")
    grid = data.pivot(index="month", columns="year", values="temp_anomaly_c")
    fig, ax = plt.subplots(figsize=(12, 3.6))
    image = ax.imshow(
        grid.to_numpy(), aspect="auto", cmap="RdBu_r", norm=TwoSlopeNorm(vcenter=0, vmin=-5, vmax=5)
    )
    ax.set_yticks(
        range(12),
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        fontsize=8,
    )
    years = grid.columns.to_numpy()
    ticks = np.arange(0, len(years), 5)
    ax.set_xticks(ticks, years[ticks])
    ax.set_title(f"{city['city'].iloc[0]}: monthly temperature anomaly vs. 1991-2020 normal")
    fig.colorbar(image, ax=ax, label="°C", fraction=0.02, pad=0.01)
    fig.savefig(path)
    plt.close(fig)


def build_report(db_path: Path, out_dir: Path, heatmap_city: str = "madrid") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    warming_stripes(db_path, out_dir / "warming_stripes.png")
    hot_days(db_path, out_dir / "hot_days.png")
    monthly_heatmap(db_path, heatmap_city, out_dir / f"monthly_anomalies_{heatmap_city}.png")
