SELECT
  SHA1(mst.measurement_type_code) AS id_dim__weather__knmi_measurement_type

, mst.measurement_type_code
, mst.measurement_type_name
, mst.measurement_type_desc
, mst.unit
, mst.measurement_type_sort
FROM
  {{ ref('int__weather__knmi_measurement_type') }} AS mst

UNION ALL

SELECT
  CAST(unk.unknown_id AS VARCHAR(40))    AS id_dim__weather__knmi_measurement_type

-- Attributes. Cast to the widths the _conf YAML declares: stg__seed__unknown is wider.
, CAST(unk.unknown_code AS VARCHAR(10))  AS measurement_type_code
, CAST(unk.unknown_name AS VARCHAR(50))  AS measurement_type_name
, CAST(unk.unknown_desc AS VARCHAR(200)) AS measurement_type_desc
, CAST('' AS VARCHAR(10))                AS unit
, CAST(-1 AS INTEGER)                    AS measurement_type_sort
FROM
  {{ ref('stg__seed__unknown') }} AS unk
