-- heatwave = at least N days in a row with Tmax above the city's 90th percentile for that
-- month (1991-2020). gaps and islands: date minus row_number is constant within a run.
with hot_days as (
    select
        d.city_id,
        d.weather_date,
        d.temp_max_c,
        n.temp_max_p90_c
    from {{ ref('fct_daily_weather') }} as d
    inner join {{ ref('mart_climate_normals') }} as n using (city_id, month)
    where d.temp_max_c > n.temp_max_p90_c
),

islands as (
    select
        *,
        date_diff('day', date '1970-01-01', weather_date)
            - row_number() over (partition by city_id order by weather_date) as island_id
    from hot_days
)

select
    city_id || '_' || strftime(min(weather_date), '%Y%m%d') as heatwave_id,
    city_id,
    min(weather_date) as start_date,
    max(weather_date) as end_date,
    year(min(weather_date)) as year,
    count(*) as duration_days,
    max(temp_max_c) as peak_temp_max_c,
    avg(temp_max_c - temp_max_p90_c) as mean_excess_c
from islands
group by city_id, island_id
having count(*) >= {{ var('heatwave_min_days') }}
