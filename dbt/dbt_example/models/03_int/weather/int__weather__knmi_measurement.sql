-- One row per station per hour per measurement type: the wide staging row unpivoted into the
-- long shape the fact uses. The code list comes from seed_knmi_measurement_type through the
-- intermediate model, so staging is scanned once and a new measurement type is a seed row plus
-- one CASE branch. An hour without a value for a measurement (the API leaves it empty) gets no row.
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
  , mst.measurement_type_code
  , CASE mst.measurement_type_code
      WHEN 'T' THEN obs.temperature_celsius
      WHEN 'FH' THEN obs.wind_speed_ms
      WHEN 'RH' THEN obs.precipitation_mm
      WHEN 'Q' THEN obs.global_radiation_jcm2
      WHEN 'U' THEN obs.relative_humidity_pct
    END AS measurement_value
  FROM
    cte_observation AS obs

    CROSS JOIN {{ ref('int__weather__knmi_measurement_type') }} AS mst

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
