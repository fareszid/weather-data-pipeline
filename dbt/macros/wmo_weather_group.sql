{#- map WMO weather codes to a few readable groups -#}
{% macro wmo_weather_group(code) -%}
    case
        when {{ code }} in (0, 1) then 'Clear'
        when {{ code }} in (2, 3) then 'Cloudy'
        when {{ code }} in (45, 48) then 'Fog'
        when {{ code }} between 51 and 57 then 'Drizzle'
        when {{ code }} between 61 and 67 or {{ code }} between 80 and 82 then 'Rain'
        when {{ code }} between 71 and 77 or {{ code }} in (85, 86) then 'Snow'
        when {{ code }} between 95 and 99 then 'Thunderstorm'
        else 'Unknown'
    end
{%- endmacro %}
