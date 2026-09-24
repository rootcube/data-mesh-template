SELECT
  CAST(src.unknown_id AS INTEGER)         AS unknown_id
, CAST(src.unknown_code AS VARCHAR(20))   AS unknown_code
, CAST(src.unknown_name AS VARCHAR(200))  AS unknown_name
, CAST(src.unknown_desc AS VARCHAR(2000)) AS unknown_desc
, CAST(src.unknown_date AS DATE)          AS unknown_date
, CAST(src.unknown_sort AS INTEGER)       AS unknown_sort
FROM
  {{ ref('seed_unknown') }} AS src
