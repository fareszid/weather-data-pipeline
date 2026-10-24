-- daily weather with calendar fields and climate index flags (ETCCDI thresholds)
select
    w.city_id,
    w.weather_date,
    year(w.weather_date) as year,
    month(w.weather_date) as month,
    w.temp_max_c,
    w.temp_min_c,
    w.temp_mean_c,
    w.feels_like_max_c,
    w.temp_max_c - w.temp_min_c as temp_range_c,
    w.precipitation_mm,
    w.snowfall_cm,
    w.wind_max_kmh,
    w.sunshine_hours,
    w.weather_code,
    {{ wmo_weather_group('w.weather_code') }} as weather_group,
    w.temp_max_c >= 30 as is_hot_day,
    w.temp_min_c >= 20 as is_tropical_night,
    w.temp_min_c < 0 as is_frost_day,
    w.precipitation_mm >= 1 as is_wet_day,
    w.loaded_at
from {{ ref('stg_open_meteo__daily_weather') }} as w
