-- the daily minimum should never be above the maximum
select city_id, weather_date, temp_min_c, temp_max_c
from {{ ref('fct_daily_weather') }}
where temp_min_c > temp_max_c + 0.05
