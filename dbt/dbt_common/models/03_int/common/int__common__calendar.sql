{{
    config(
        enabled=true,
        materialized='table',
        tags=['owner=public', 'system=common', 'category=date'],
        unique_key=['date']
    )
}}

WITH cte_date_range AS (
  SELECT
    day
  , date
  , date_time
  FROM
    {{ ref('int__common__date') }}

  UNION ALL

  SELECT
    0                                       AS day
  , CAST('1900-01-01' AS DATE)              AS date
  , CAST('1900-01-01 00:00:00' AS DATETIME) AS date_time

  UNION ALL

  SELECT
    99999999                                AS day
  , CAST('9999-12-31' AS DATE)              AS date
  , CAST('9999-12-31 23:59:59' AS DATETIME) AS date_time
)

, cte_month_label AS (
  SELECT
    month_nr   AS month_nr
  , month_code AS month_abbr
  , month_name AS month_name
  FROM
    {{ ref('stg__seed__month') }}
)

, cte_weekday_label AS (
  SELECT
    weekday_nr   AS day_nr
  , weekday_code AS day_abbr
  , weekday_name AS day_name
  FROM
    {{ ref('stg__seed__weekday') }}
)

, cte_holidays AS (
  SELECT
    date         AS date
  , holiday_name AS holiday_name
  FROM
    {{ ref('int__common__holiday') }}
)

, cte_calendar AS (
  SELECT
    date                                                         AS date
  , date_time                                                    AS date_time
  , {{ dbt_common.date_simple('date') }}                         AS date_simple

  -- Calendar
  , CAST(DATE_PART('year', date) AS INTEGER)                     AS year
  , CAST(DATE_PART('quarter', date) AS INTEGER)                  AS quarter
  , CAST(DATE_PART('month', date) AS INTEGER)                    AS month
  , CAST(DATE_PART('weekofyear', date) AS INTEGER)               AS week --> Follows the WEEK_OF_YEAR_POLICY session parameter; iso_week below does not

  -- ISO
  , CAST({{ dbt_common.iso_year('date') }} AS INTEGER)           AS iso_year
  , CAST({{ dbt_common.iso_week('date') }} AS INTEGER)           AS iso_week

  -- Days
  , CAST(DATE_PART('dayofyear', date) AS INTEGER)                AS day_of_year
  , CAST(DATE_PART('dayofmonth', date) AS INTEGER)               AS day_of_month
  , CAST(DATEDIFF('day', '1900-01-01', date) AS INTEGER) % 7 + 1 AS day_of_week --> Independent of config (https://docs.snowflake.com/en/sql-reference/parameters.html#label-week-start)
  FROM
    cte_date_range
)


SELECT
-- Dates
  cal.date
, cal.date_time
, cal.date_simple

-- Default Attributes
, CAST(cal.year AS INTEGER)                                                                                                                                                    AS year_nr
, CAST(CASE WHEN cal.month < 4 THEN cal.year - 1 ELSE cal.year END AS INTEGER)                                                                                                 AS base_year
, CAST(cal.quarter AS INTEGER)                                                                                                                                                 AS quarter_nr
, CAST(cal.month AS INTEGER)                                                                                                                                                   AS month_nr
, CAST(cal.week AS INTEGER)                                                                                                                                                    AS week_nr
, CAST(cal.iso_year AS INTEGER)                                                                                                                                                AS iso_year_nr
, CAST(cal.iso_week AS INTEGER)                                                                                                                                                AS iso_week_nr

-- Combined Attributes
, CAST(cal.year * 10000 + cal.quarter * 100 + cal.month AS INTEGER)                                                                                                            AS year_quarter_month_nr
, CAST(cal.year * 100 + cal.quarter AS INTEGER)                                                                                                                                AS year_quarter_nr
, CAST(cal.year * 100 + cal.month AS INTEGER)                                                                                                                                  AS year_month_nr
, CAST(cal.year * 100 + cal.week AS INTEGER)                                                                                                                                   AS year_week_nr
, CAST(cal.iso_year * 100 + cal.iso_week AS INTEGER)                                                                                                                           AS iso_year_week_nr

-- Specific Days
, CAST(cal.day_of_year AS INTEGER)                                                                                                                                             AS day_of_year_nr
, CAST(cal.day_of_month AS INTEGER)                                                                                                                                            AS day_of_month_nr
, CAST(cal.day_of_week AS INTEGER)                                                                                                                                             AS day_of_week_nr
, CAST(ROW_NUMBER() OVER (PARTITION BY cal.iso_year ORDER BY cal.date ASC) AS INTEGER)                                                                                         AS iso_year_day_nr

-- Codes and Descriptions
, CAST(CONCAT('Y', cal.year) AS VARCHAR(10))                                                                                                                                   AS year_code
, CAST(CONCAT('Year ', cal.year) AS VARCHAR(10))                                                                                                                               AS year_name

, CAST(CONCAT('Q', LPAD(CAST(cal.quarter AS VARCHAR), 1, '0')) AS VARCHAR(10))                                                                                                 AS quarter_code
, CAST(CONCAT('Quarter ', cal.quarter) AS VARCHAR(10))                                                                                                                         AS quarter_name

, CAST(CONCAT('M', LPAD(CAST(cal.month AS VARCHAR), 2, '0')) AS VARCHAR(10))                                                                                                   AS month_code
, CAST(mlb.month_name AS VARCHAR(10))                                                                                                                                          AS month_name
, CAST(mlb.month_abbr AS VARCHAR(10))                                                                                                                                          AS month_abbr

, CAST(CONCAT('W', LPAD(CAST(cal.week AS VARCHAR), 2, '0')) AS VARCHAR(10))                                                                                                    AS week_code
, CAST(CONCAT('Week ', cal.week) AS VARCHAR(20))                                                                                                                               AS week_desc

, CAST(CONCAT('Y', cal.iso_year) AS VARCHAR(10))                                                                                                                               AS iso_year_code
, CAST(CONCAT('ISO Year ', cal.iso_year) AS VARCHAR(20))                                                                                                                       AS iso_year_desc
, CAST(CONCAT('W', LPAD(CAST(cal.iso_week AS VARCHAR), 2, '0')) AS VARCHAR(10))                                                                                                AS iso_week_code
, CAST(CONCAT('ISO Week ', cal.iso_week) AS VARCHAR(20))                                                                                                                       AS iso_week_desc

, CAST(CONCAT('YD', LPAD(CAST(cal.day_of_year AS VARCHAR), 3, '0')) AS VARCHAR(10))                                                                                            AS year_day_code
, CAST(CONCAT('MD', LPAD(CAST(cal.day_of_month AS VARCHAR), 2, '0')) AS VARCHAR(10))                                                                                           AS month_day_code
, CAST(CONCAT('WD', LPAD(CAST(cal.day_of_week AS VARCHAR), 2, '0')) AS VARCHAR(10))                                                                                            AS week_day_code

, CAST(dlb.day_name AS VARCHAR(10))                                                                                                                                            AS week_day_name
, CAST(dlb.day_abbr AS VARCHAR(10))                                                                                                                                            AS week_day_abbr

-- Indicators
, CAST(CASE WHEN cal.date = CAST(DATE_TRUNC('year', NULLIF(cal.date, '9999-12-31')) AS DATE) THEN 'Y' ELSE 'N' END AS CHAR(1))                                                 AS is_first_day_of_year
, CAST(CASE WHEN cal.date = CAST(DATE_TRUNC('quarter', NULLIF(cal.date, '9999-12-31')) AS DATE) THEN 'Y' ELSE 'N' END AS CHAR(1))                                              AS is_first_day_of_quarter
, CAST(CASE WHEN cal.date = CAST(DATE_TRUNC('month', NULLIF(cal.date, '9999-12-31')) AS DATE) THEN 'Y' ELSE 'N' END AS CHAR(1))                                                AS is_first_day_of_month
, CAST(CASE WHEN cal.day_of_week = 1 THEN 'Y' ELSE 'N' END AS CHAR(1))                                                                                                         AS is_first_day_of_week

, CAST(CASE WHEN cal.date = CAST(DATE_TRUNC('year', NULLIF(cal.date, '9999-12-31')) + INTERVAL '1 year' - INTERVAL '1 day' AS DATE) THEN 'Y' ELSE 'N' END AS CHAR(1))          AS is_last_day_of_year
, CAST(CASE WHEN cal.date = CAST(DATE_TRUNC('quarter', NULLIF(cal.date, '9999-12-31')) + INTERVAL '1 quarter' - INTERVAL '1 day' AS DATE) THEN 'Y' ELSE 'N' END AS CHAR(1))    AS is_last_day_of_quarter
, CAST(CASE WHEN cal.date = CAST(DATE_TRUNC('month', NULLIF(cal.date, '9999-12-31')) + INTERVAL '1 month' - INTERVAL '1 day' AS DATE) THEN 'Y' ELSE 'N' END AS CHAR(1))        AS is_last_day_of_month
, CAST(CASE WHEN cal.day_of_week = 7 THEN 'Y' ELSE 'N' END AS CHAR(1))                                                                                                         AS is_last_day_of_week

, CAST(CASE WHEN (cal.year % 4 = 0 AND cal.year % 100 <> 0) OR cal.year % 400 = 0 THEN 'Y' ELSE 'N' END AS CHAR(1))                                                            AS is_leap_year
, CAST(CASE WHEN cal.day_of_month = 29 AND cal.month = 2 THEN 'Y' ELSE 'N' END AS CHAR(1))                                                                                     AS is_leap_day

, CAST(CASE WHEN cal.day_of_week IN (6, 7) THEN 'Y' ELSE 'N' END AS CHAR(1))                                                                                                   AS is_weekend
, CAST(CASE WHEN cal.day_of_week IN (1, 2, 3, 4, 5) THEN 'Y' ELSE 'N' END AS CHAR(1))                                                                                          AS is_workday

-- Additional Dates
, CAST(DATE_TRUNC('year', NULLIF(cal.date, '9999-12-31')) AS DATE)                                                                                                             AS first_date_of_year
, CAST(DATE_TRUNC('quarter', NULLIF(cal.date, '9999-12-31')) AS DATE)                                                                                                          AS first_date_of_quarter
, CAST(DATE_TRUNC('month', NULLIF(cal.date, '9999-12-31')) AS DATE)                                                                                                            AS first_date_of_month
, CAST(NULLIF(cal.date, '9999-12-31') + (1 - cal.day_of_week) AS DATE)                                                                                                         AS first_date_of_week

, CAST(DATE_TRUNC('year', NULLIF(cal.date, '9999-12-31')) + INTERVAL '1 year' - INTERVAL '1 day' AS DATE)                                                                      AS last_date_of_year
, CAST(DATE_TRUNC('quarter', NULLIF(cal.date, '9999-12-31')) + INTERVAL '1 quarter' - INTERVAL '1 day' AS DATE)                                                                AS last_date_of_quarter
, CAST(DATE_TRUNC('month', NULLIF(cal.date, '9999-12-31')) + INTERVAL '1 month' - INTERVAL '1 day' AS DATE)                                                                    AS last_date_of_month
, CAST(NULLIF(cal.date, '9999-12-31') + (7 - cal.day_of_week) AS DATE)                                                                                                         AS last_date_of_week

-- Sequences
, CAST(CASE WHEN cal.date IN ('1900-01-01', '9999-12-31') THEN NULL ELSE DENSE_RANK() OVER (PARTITION BY NULL ORDER BY cal.iso_year ASC) - 1 END AS INTEGER)                   AS iso_year_sort
, CAST(CASE WHEN cal.date IN ('1900-01-01', '9999-12-31') THEN NULL ELSE DENSE_RANK() OVER (PARTITION BY NULL ORDER BY cal.year ASC) - 1 END AS INTEGER)                       AS year_sort
, CAST(CASE WHEN cal.date IN ('1900-01-01', '9999-12-31') THEN NULL ELSE DENSE_RANK() OVER (PARTITION BY NULL ORDER BY cal.year ASC, cal.quarter ASC) - 1 END AS INTEGER)      AS quarter_sort
, CAST(CASE WHEN cal.date IN ('1900-01-01', '9999-12-31') THEN NULL ELSE DENSE_RANK() OVER (PARTITION BY NULL ORDER BY cal.year ASC, cal.month ASC) - 1 END AS INTEGER)        AS month_sort
, CAST(CASE WHEN cal.date IN ('1900-01-01', '9999-12-31') THEN NULL ELSE DENSE_RANK() OVER (PARTITION BY NULL ORDER BY cal.date ASC) - 1 END AS INTEGER)                       AS day_sort
, CAST(CASE WHEN cal.date IN ('1900-01-01', '9999-12-31') THEN NULL ELSE DENSE_RANK() OVER (PARTITION BY NULL ORDER BY cal.iso_year ASC, cal.iso_week ASC) - 1 END AS INTEGER) AS week_sort

, COALESCE(hol.holiday_name IS NOT NULL, FALSE)                                                                                                                                AS is_holiday
, hol.holiday_name

-- add indicators for high generation and consumption days, based on month and weekday/weekend for worst case day profiles
, COALESCE(mlb.month_nr IN (5, 6, 7, 8) AND is_weekend = 'Y', FALSE)                                                                                                           AS is_high_generation_day
, COALESCE(mlb.month_nr IN (12, 1, 2, 3) AND is_workday = 'Y', FALSE)                                                                                                          AS is_high_consumption_day

FROM
  cte_calendar AS cal

  LEFT JOIN cte_month_label AS mlb
    ON mlb.month_nr = cal.month

  LEFT JOIN cte_weekday_label AS dlb
    ON dlb.day_nr = cal.day_of_week

  LEFT JOIN cte_holidays AS hol
    ON hol.date = cal.date
