SELECT
  CAST(src.station_code AS INTEGER)      AS station_code
, CAST(src.station_name AS VARCHAR(50))  AS station_name
, CAST(src.longitude AS NUMERIC(6, 3))   AS longitude
, CAST(src.latitude AS NUMERIC(6, 3))    AS latitude
, CAST(src.elevation_m AS NUMERIC(6, 2)) AS elevation_m
FROM
  {{ ref('seed_knmi_station') }} AS src
