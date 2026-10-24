-- two heatwaves of the same city should never overlap
select a.heatwave_id, b.heatwave_id as overlapping_id
from {{ ref('mart_heatwaves') }} as a
inner join {{ ref('mart_heatwaves') }} as b
    on a.city_id = b.city_id
    and a.heatwave_id < b.heatwave_id
    and a.start_date <= b.end_date
    and b.start_date <= a.end_date
