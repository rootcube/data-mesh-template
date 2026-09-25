SELECT
  SHA1(CAST(stn.station_code AS VARCHAR)) AS id_dim__weather__station

, stn.station_code
, stn.station_name
, stn.longitude
, stn.latitude
, stn.elevation_m
FROM
  {{ ref('int__weather__station') }} AS stn

UNION ALL

SELECT
  CAST(unk.unknown_id AS VARCHAR) AS id_dim__weather__station

-- Attributes
, CAST(unk.unknown_id AS INTEGER) AS station_code
, unk.unknown_name                AS station_name
, NULL                            AS longitude
, NULL                            AS latitude
, NULL                            AS elevation_m
FROM
  {{ ref('stg__seed__unknown') }} AS unk
