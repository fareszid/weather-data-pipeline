-- no dates in the future
select city_id, weather_date
from {{ ref('fct_daily_weather') }}
where weather_date > current_date
