-- one row per city and year: climate indicators and anomaly vs. the baseline
{% set start_year = var('baseline_start_year') %}
{% set end_year = var('baseline_end_year') %}

with annual as (
    select
        city_id,
        year,
        count(*) as days_observed,
        avg(temp_mean_c) as temp_mean_c,
        max(temp_max_c) as temp_max_record_c,
        min(temp_min_c) as temp_min_record_c,
        sum(precipitation_mm) as precipitation_mm,
        count(*) filter (where is_hot_day) as hot_days,
        count(*) filter (where is_tropical_night) as tropical_nights,
        count(*) filter (where is_frost_day) as frost_days,
        count(*) filter (where is_wet_day) as wet_days,
        sum(sunshine_hours) as sunshine_hours
    from {{ ref('fct_daily_weather') }}
    group by city_id, year
),

baseline as (
    select city_id, avg(temp_mean_c) as baseline_temp_mean_c
    from annual
    where year between {{ start_year }} and {{ end_year }} and days_observed >= 365
    group by city_id
),

heatwaves as (
    select city_id, year, count(*) as heatwave_events, sum(duration_days) as heatwave_days
    from {{ ref('mart_heatwaves') }}
    group by city_id, year
)

select
    a.*,
    a.days_observed >= 365 as is_complete_year,
    a.temp_mean_c - b.baseline_temp_mean_c as temp_anomaly_c,
    coalesce(h.heatwave_events, 0) as heatwave_events,
    coalesce(h.heatwave_days, 0) as heatwave_days,
    case when a.days_observed >= 365 then
        rank() over (
            partition by a.city_id, a.days_observed >= 365 order by a.temp_mean_c desc
        )
    end as warmth_rank
from annual as a
left join baseline as b using (city_id)
left join heatwaves as h using (city_id, year)
