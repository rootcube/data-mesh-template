{{
    config(
        materialized='table',
        unique_key=['station_code', 'observed_at']
    )
}}

-- KNMI hourly observations, typed and converted to SI-ish units. The API's hour 1..24 is the
-- hour *ending* at that time, so hour 24 of 2024-01-01 becomes 2024-01-02 00:00.
WITH cte_source AS (

  SELECT
    src.station_code
  , src.date
  , src.hour
  , src.t
  , src.fh
  , src.rh
  , src.q
  , src.u
  , src._dlt_load_id
  FROM
    {{ source('knmi', 'climate_hourly') }} AS src

)

SELECT
  CAST(obs.station_code AS INTEGER)                                                         AS station_code
, DATEADD('hour', CAST(obs.hour AS INTEGER), CAST(CAST(obs.date AS DATE) AS TIMESTAMP_NTZ)) AS observed_at
, CAST(obs.t AS INTEGER) / 10.0                                                             AS temperature_celsius
, CAST(obs.fh AS INTEGER) / 10.0                                                            AS wind_speed_ms
, CASE
    WHEN CAST(obs.rh AS INTEGER) = -1 THEN 0.05
    ELSE CAST(obs.rh AS INTEGER) / 10.0
  END                                                                                       AS precipitation_mm
, CAST(obs.q AS INTEGER)                                                                    AS global_radiation_jcm2
, CAST(obs.u AS INTEGER)                                                                    AS relative_humidity_pct
, obs._dlt_load_id
FROM
  cte_source AS obs
