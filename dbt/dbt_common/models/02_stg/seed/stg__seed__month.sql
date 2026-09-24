SELECT
  CAST(src.month_nr AS INTEGER)       AS month_nr
, CAST(src.month_code AS VARCHAR(3))  AS month_code
, CAST(src.month_name AS VARCHAR(20)) AS month_name
FROM
  {{ ref('seed_month') }} AS src
