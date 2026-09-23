{{
    config(
        enabled=true,
        materialized='table',
        tags=['owner=public', 'system=generic', 'category=date'],
        unique_key=['date']
    )
}}

SELECT
  day
, CAST(DATEADD('day', DAY, '1900-01-01') AS DATE)     AS date
, CAST(DATEADD('day', DAY, '1900-01-01') AS DATETIME) AS date_time
, {{ dbt_common.utc_today() }}                        AS date_current
, DATE_TRUNC('YEAR', {{ dbt_common.utc_today() }})    AS date_base
, DATEADD('YEAR', (-10), date_base)                   AS date_start -- 10 years back
, DATEADD('YEAR', (10 + 1), date_base) - 1            AS date_end   -- 10 years forward

FROM
  (SELECT SEQ4() AS day FROM TABLE(GENERATOR(ROWCOUNT => 2958464))) -- days 1900-01-01..9999-12-31, capped by WHERE below

WHERE 1 = 1
  AND day <= DATEDIFF('day', '1900-01-01', '9999-12-31') --> prevent non-existing dates
  AND date BETWEEN date_start AND date_end -- Sliding years
