SELECT
  SHA1(mst.measurement_type_code) AS id_dim__weather__measurement_type

, mst.measurement_type_code
, mst.measurement_type_name
, mst.measurement_type_desc
, mst.unit
, mst.measurement_type_sort
FROM
  {{ ref('int__weather__measurement_type') }} AS mst

UNION ALL

SELECT
  CAST(unk.unknown_id AS VARCHAR) AS id_dim__weather__measurement_type

-- Attributes
, unk.unknown_code                AS measurement_type_code
, unk.unknown_name                AS measurement_type_name
, unk.unknown_desc                AS measurement_type_desc
, ''                              AS unit
, -1                              AS measurement_type_sort
FROM
  {{ ref('stg__seed__unknown') }} AS unk
