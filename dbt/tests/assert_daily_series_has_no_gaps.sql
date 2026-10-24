-- every city should have one row per day between its first and last date
select
    city_id,
    min(weather_date) as first_date,
    max(weather_date) as last_date,
    count(*) as days_present,
    date_diff('day', min(weather_date), max(weather_date)) + 1 as days_expected
from {{ ref('fct_daily_weather') }}
group by city_id
having count(*) != date_diff('day', min(weather_date), max(weather_date)) + 1
