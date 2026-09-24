SELECT
  UPPER(CAST(src.weekday_nr AS INTEGER)) AS weekday_nr
, CAST(src.weekday_code AS VARCHAR(3))   AS weekday_code
, CAST(src.weekday_name AS VARCHAR(10))  AS weekday_name
FROM
  {{ ref('seed_weekday') }} AS src
