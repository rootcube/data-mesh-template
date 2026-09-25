{{
    config(
        materialized='table',
        unique_key=['id_fct__weather__knmi_measurement']
    )
}}

-- One row per station per hour per measurement type. `observed_at` is the end of the hour, as
-- KNMI reports it; the calendar and time keys point at the start of that hour, so a roll-up per
-- calendar day lands on the day the hour belongs to.
WITH cte_observation AS (

  SELECT
    obs.station_code
  , obs.observed_at
  , DATEADD('hour', -1, obs.observed_at) AS hour_start_at
  , obs.measurement_type_code
  , obs.measurement_value
  FROM
    {{ ref('int__weather__knmi_measurement') }} AS obs

)

SELECT
  {{ dbt_utils.generate_surrogate_key(['obs.station_code', 'obs.observed_at', 'obs.measurement_type_code']) }} AS id_fct__weather__knmi_measurement
, COALESCE(stn.id_dim__weather__knmi_station, '-2')                                                            AS id_dim__weather__knmi_station
, COALESCE(mst.id_dim__weather__knmi_measurement_type, '-2')                                                   AS id_dim__weather__knmi_measurement_type
, CAST(TO_CHAR(obs.hour_start_at, 'YYYYMMDD') AS INTEGER)                                                      AS id_dim__common__calendar
, CAST(TO_CHAR(obs.hour_start_at, 'HH24MISS') AS INTEGER)                                                      AS id_dim__common__time
, obs.observed_at

-- Measures
, obs.measurement_value
FROM
  cte_observation AS obs

  LEFT JOIN {{ ref('dim__weather__knmi_station') }} AS stn
    ON stn.station_code = obs.station_code

  LEFT JOIN {{ ref('dim__weather__knmi_measurement_type') }} AS mst
    ON mst.measurement_type_code = obs.measurement_type_code
