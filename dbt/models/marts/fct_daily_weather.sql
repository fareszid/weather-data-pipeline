{{
    config(
        materialized='incremental',
        unique_key=['city_id', 'weather_date'],
        incremental_strategy='delete+insert',
        on_schema_change='fail'
    )
}}

-- incremental: only process rows loaded since the last run
select *
from {{ ref('int_daily_weather_enriched') }}
{% if is_incremental() %}
where loaded_at > (select max(loaded_at) from {{ this }})
{% endif %}
