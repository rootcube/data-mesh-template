{{
    config(
        unique_key=['station_code', 'observed_at', 'measurement_type_code']
    )
}}

/*
  Data product: Station weather
  Purpose: hourly KNMI measurements per station for the weather dashboard
  (exposures/weather_dashboard.yml): the observation star flattened into one row per station
  per hour per measurement type, with the station and measurement-type attributes alongside.
*/

SELECT
  stn.station_code
, stn.station_name
, stn.latitude
, stn.longitude
, fct.observed_at
, mst.measurement_type_code
, mst.measurement_type_name
, mst.unit
, fct.measurement_value
FROM
  {{ ref('fct__weather__knmi_measurement') }} AS fct

  INNER JOIN {{ ref('dim__weather__knmi_station') }} AS stn
    ON stn.id_dim__weather__knmi_station = fct.id_dim__weather__knmi_station

  INNER JOIN {{ ref('dim__weather__knmi_measurement_type') }} AS mst
    ON mst.id_dim__weather__knmi_measurement_type = fct.id_dim__weather__knmi_measurement_type
