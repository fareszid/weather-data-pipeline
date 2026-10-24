-- one row per city and month; the current month is flagged as incomplete
select
    city_id,
    year,
    month,
    make_date(year, month, 1) as month_start,
    count(*) as days_observed,
    count(*) = day(last_day(make_date(year, month, 1))) as is_complete_month,
    avg(temp_mean_c) as temp_mean_c,
    avg(temp_max_c) as temp_max_c,
    avg(temp_min_c) as temp_min_c,
    max(temp_max_c) as temp_max_record_c,
    sum(precipitation_mm) as precipitation_mm,
    count(*) filter (where is_wet_day) as wet_days,
    count(*) filter (where is_hot_day) as hot_days,
    count(*) filter (where is_tropical_night) as tropical_nights,
    count(*) filter (where is_frost_day) as frost_days,
    sum(sunshine_hours) as sunshine_hours
from {{ ref('int_daily_weather_enriched') }}
group by city_id, year, month
