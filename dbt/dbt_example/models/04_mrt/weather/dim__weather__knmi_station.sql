SELECT
  SHA1(CAST(stn.station_code AS VARCHAR)) AS id_dim__weather__knmi_station

, stn.station_code
, stn.station_name
, stn.longitude
, stn.latitude
, stn.elevation_m
FROM
  {{ ref('int__weather__knmi_station') }} AS stn

UNION ALL

SELECT
  CAST(unk.unknown_id AS VARCHAR(40))   AS id_dim__weather__knmi_station

-- Attributes. Cast to the widths the _conf YAML declares: stg__seed__unknown is wider.
, CAST(unk.unknown_id AS INTEGER)       AS station_code
, CAST(unk.unknown_name AS VARCHAR(50)) AS station_name
, CAST(NULL AS NUMERIC(6, 3))           AS longitude
, CAST(NULL AS NUMERIC(6, 3))           AS latitude
, CAST(NULL AS NUMERIC(6, 2))           AS elevation_m
FROM
  {{ ref('stg__seed__unknown') }} AS unk
