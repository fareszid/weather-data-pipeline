-- each month vs. its 1991-2020 normal
select
    m.city_id,
    m.month_start,
    m.year,
    m.month,
    m.is_complete_month,
    m.temp_mean_c,
    n.temp_mean_c as normal_temp_mean_c,
    m.temp_mean_c - n.temp_mean_c as temp_anomaly_c,
    m.precipitation_mm,
    n.precipitation_mm as normal_precipitation_mm,
    case
        when n.precipitation_mm > 0 and m.is_complete_month
            then 100.0 * (m.precipitation_mm - n.precipitation_mm) / n.precipitation_mm
    end as precipitation_anomaly_pct,
    m.hot_days,
    m.tropical_nights,
    m.frost_days,
    m.sunshine_hours
from {{ ref('int_monthly_weather') }} as m
inner join {{ ref('mart_climate_normals') }} as n using (city_id, month)
