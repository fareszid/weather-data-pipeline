-- monthly normals per city over the baseline period (default 1991-2020).
-- temp_max_p90_c is the threshold used to detect heatwaves.
{% set start_year = var('baseline_start_year') %}
{% set end_year = var('baseline_end_year') %}

with monthly as (
    select *
    from {{ ref('int_monthly_weather') }}
    where year between {{ start_year }} and {{ end_year }} and is_complete_month
),

daily_thresholds as (
    select
        city_id,
        month,
        quantile_cont(temp_max_c, 0.9) as temp_max_p90_c
    from {{ ref('int_daily_weather_enriched') }}
    where year between {{ start_year }} and {{ end_year }}
    group by city_id, month
)

select
    m.city_id,
    m.month,
    count(*) as baseline_years,
    avg(m.temp_mean_c) as temp_mean_c,
    avg(m.temp_max_c) as temp_max_c,
    avg(m.temp_min_c) as temp_min_c,
    avg(m.precipitation_mm) as precipitation_mm,
    avg(m.wet_days) as wet_days,
    avg(m.sunshine_hours) as sunshine_hours,
    t.temp_max_p90_c
from monthly as m
inner join daily_thresholds as t using (city_id, month)
group by m.city_id, m.month, t.temp_max_p90_c
