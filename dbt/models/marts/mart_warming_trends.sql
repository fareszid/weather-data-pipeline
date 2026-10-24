-- warming per city: linear trend of the yearly mean temperature, and the last 10 complete
-- years vs. the baseline
{% set start_year = var('baseline_start_year') %}
{% set end_year = var('baseline_end_year') %}

with complete_years as (
    select * from {{ ref('mart_annual_summary') }} where is_complete_year
),

recent as (
    select city_id, max(year) as last_year from complete_years group by city_id
)

select
    y.city_id,
    c.city,
    c.country,
    c.koppen_climate,
    min(y.year) as first_year,
    max(y.year) as last_year,
    10 * regr_slope(y.temp_mean_c, y.year) as trend_c_per_decade,
    regr_r2(y.temp_mean_c, y.year) as trend_r2,
    avg(y.temp_mean_c) filter (where y.year between {{ start_year }} and {{ end_year }})
        as baseline_temp_mean_c,
    avg(y.temp_mean_c) filter (where y.year > r.last_year - 10) as last_10y_temp_mean_c,
    avg(y.temp_mean_c) filter (where y.year > r.last_year - 10)
        - avg(y.temp_mean_c) filter (where y.year between {{ start_year }} and {{ end_year }})
        as last_10y_vs_baseline_c,
    avg(y.hot_days) filter (where y.year between {{ start_year }} and {{ end_year }})
        as baseline_hot_days,
    avg(y.hot_days) filter (where y.year > r.last_year - 10) as last_10y_hot_days,
    arg_max(y.year, y.temp_mean_c) as warmest_year
from complete_years as y
inner join recent as r using (city_id)
inner join {{ ref('dim_cities') }} as c using (city_id)
group by y.city_id, c.city, c.country, c.koppen_climate
