{{
    config(
        materialized='table',
        unique_key=['station_code', 'observed_at', 'measurement_type_code']
    )
}}

-- One row per station per hour per measurement type: the wide staging row unpivoted into the
-- long shape the fact uses, keyed by the KNMI variable codes of seed_knmi_measurement_type. An hour
-- without a value for a measurement (the API leaves it empty) gets no row.
WITH cte_observation AS (

  SELECT
    src.station_code
  , src.observed_at
  , src.temperature_celsius
  , src.wind_speed_ms
  , src.precipitation_mm
  , src.global_radiation_jcm2
  , src.relative_humidity_pct
  FROM
    {{ ref('stg__knmi__climate_hourly') }} AS src

)

, cte_measurement AS (

  SELECT
    obs.station_code
  , obs.observed_at
  , 'T'                     AS measurement_type_code
  , obs.temperature_celsius AS measurement_value
  FROM
    cte_observation AS obs

  UNION ALL

  SELECT
    obs.station_code
  , obs.observed_at
  , 'FH'              AS measurement_type_code
  , obs.wind_speed_ms AS measurement_value
  FROM
    cte_observation AS obs

  UNION ALL

  SELECT
    obs.station_code
  , obs.observed_at
  , 'RH'                 AS measurement_type_code
  , obs.precipitation_mm AS measurement_value
  FROM
    cte_observation AS obs

  UNION ALL

  SELECT
    obs.station_code
  , obs.observed_at
  , 'Q'                       AS measurement_type_code
  , obs.global_radiation_jcm2 AS measurement_value
  FROM
    cte_observation AS obs

  UNION ALL

  SELECT
    obs.station_code
  , obs.observed_at
  , 'U'                       AS measurement_type_code
  , obs.relative_humidity_pct AS measurement_value
  FROM
    cte_observation AS obs

)

SELECT
  msr.station_code
, msr.observed_at
, msr.measurement_type_code
, CAST(msr.measurement_value AS NUMBER(10, 2)) AS measurement_value
FROM
  cte_measurement AS msr
WHERE
  msr.measurement_value IS NOT NULL
