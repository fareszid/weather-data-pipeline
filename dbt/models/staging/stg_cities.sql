select
    city_id,
    city,
    country,
    continent,
    latitude,
    longitude,
    timezone,
    koppen_climate,
    case when latitude >= 0 then 'Northern' else 'Southern' end as hemisphere
from {{ ref('cities') }}
