SELECT
  CAST(src.measurement_type_code AS VARCHAR(10))  AS measurement_type_code
, CAST(src.measurement_type_name AS VARCHAR(50))  AS measurement_type_name
, CAST(src.measurement_type_desc AS VARCHAR(200)) AS measurement_type_desc
, CAST(src.unit AS VARCHAR(10))                   AS unit
, CAST(src.measurement_type_sort AS INTEGER)      AS measurement_type_sort
FROM
  {{ ref('seed_knmi_measurement_type') }} AS src
