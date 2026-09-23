SELECT
  CAST(src.environment_code AS VARCHAR(20))   AS environment_code
, CAST(src.environment_name AS VARCHAR(100))  AS environment_name
, CAST(src.environment_alias AS VARCHAR(100)) AS environment_alias
, CAST(src.environment_desc AS VARCHAR(400))  AS environment_desc
, CAST(src.environment_sort AS INTEGER)       AS environment_sort
FROM
  {{ ref('seed_environment') }} AS src
