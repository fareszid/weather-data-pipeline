select
    c.*,
    coverage.first_date,
    coverage.last_date,
    coverage.days_loaded
from {{ ref('stg_cities') }} as c
left join (
    select
        city_id,
        min(weather_date) as first_date,
        max(weather_date) as last_date,
        count(*) as days_loaded
    from {{ ref('stg_open_meteo__daily_weather') }}
    group by city_id
) as coverage using (city_id)
