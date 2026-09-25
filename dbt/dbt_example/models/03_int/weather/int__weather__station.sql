SELECT
  stn.station_code
, stn.station_name
, stn.longitude
, stn.latitude
, stn.elevation_m
FROM
  {{ ref('stg__seed__knmi_station') }} AS stn
