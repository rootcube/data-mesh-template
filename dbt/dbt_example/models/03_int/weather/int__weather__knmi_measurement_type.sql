SELECT
  mst.measurement_type_code
, mst.measurement_type_name
, mst.measurement_type_desc
, mst.unit
, mst.measurement_type_sort
FROM
  {{ ref('stg__seed__knmi_measurement_type') }} AS mst
