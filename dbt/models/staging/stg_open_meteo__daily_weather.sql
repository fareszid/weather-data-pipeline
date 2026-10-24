-- rename columns, convert units, keep load metadata
with source as (
    select * from {{ source('open_meteo', 'daily_weather') }}
)

select
    city_id,
    date as weather_date,
    temperature_2m_max as temp_max_c,
    temperature_2m_min as temp_min_c,
    temperature_2m_mean as temp_mean_c,
    apparent_temperature_max as feels_like_max_c,
    precipitation_sum as precipitation_mm,
    snowfall_sum as snowfall_cm,
    wind_speed_10m_max as wind_max_kmh,
    round(sunshine_duration / 3600.0, 2) as sunshine_hours,
    weather_code,
    fetched_at,
    loaded_at
from source
