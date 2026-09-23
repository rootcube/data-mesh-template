{{
    config(
        enabled=true,
        materialized='table',
        tags=['owner=public', 'system=generic', 'category=time'],
        unique_key=['time']
    )
}}


WITH cte_time_range AS (
  SELECT
    CAST(DATEADD('second', SECOND, '1900-01-01') AS TIME)     AS time
  , CAST(DATEADD('second', SECOND, '1900-01-01') AS DATETIME) AS date_time
  FROM (SELECT SEQ4() AS second FROM TABLE(GENERATOR(rowcount => 86400)))
  WHERE 1 = 1
    AND second >= 0
    AND second <= 86399
)

, cte_times AS (
  SELECT
    time                                                     AS time
  , date_time                                                AS date_time
  , CAST(REPLACE(CAST(time AS VARCHAR), ':', '') AS INTEGER) AS time_simple

  -- Calendar
  , CAST(DATE_PART('hour', date_time) AS INTEGER)            AS hour
  , CAST(DATE_PART('minute', date_time) AS INTEGER)          AS minute
  , CAST(DATE_PART('second', date_time) AS INTEGER)          AS second
  FROM
    cte_time_range
)

SELECT
  tim.time                                                                                       AS time
, tim.time_simple                                                                                AS time_simple

, TO_TIME(LPAD(tim.hour, 2, '0') || ':00:00')                                                    AS time_hour
, TO_TIME(LPAD(tim.hour, 2, '0') || ':' || LPAD(tim.minute, 2, '0') || ':00')                    AS time_minute
, tim.time                                                                                       AS time_second

-- Hour
, tim.hour                                                                                       AS hour_nr
, CAST(CONCAT('H', LPAD(tim.hour, 2, '0')) AS CHAR(3))                                           AS hour_code
, CAST(CONCAT('Hour ', LPAD(tim.hour, 2, '0')) AS CHAR(10))                                      AS hour_name
, CAST(DENSE_RANK() OVER (PARTITION BY NULL ORDER BY tim.hour ASC) AS INTEGER)                   AS hour_sort

-- Minute
, tim.minute                                                                                     AS minute_nr
, CAST(CONCAT('M', LPAD(tim.minute, 2, '0')) AS CHAR(3))                                         AS minute_code
, CAST(CONCAT('Minute ', LPAD(tim.minute, 2, '0')) AS CHAR(10))                                  AS minute_name
, CAST(DENSE_RANK() OVER (PARTITION BY tim.hour ORDER BY tim.minute ASC) AS INTEGER)             AS minute_sort

-- Second
, tim.second                                                                                     AS second_nr
, CAST(CONCAT('S', LPAD(tim.second, 2, '0')) AS CHAR(3))                                         AS second_code
, CAST(CONCAT('Second ', LPAD(tim.second, 2, '0')) AS CHAR(10))                                  AS second_name
, CAST(ROW_NUMBER() OVER (PARTITION BY tim.hour, tim.minute ORDER BY tim.second ASC) AS INTEGER) AS second_sort

-- Other
, CASE
    WHEN tim.hour >= 5 AND tim.hour <= 11 THEN 'morning'
    WHEN tim.hour >= 12 AND tim.hour <= 16 THEN 'afternoon'
    WHEN tim.hour >= 17 AND tim.hour <= 20 THEN 'evening'
    WHEN tim.hour >= 21 THEN 'night'
    WHEN tim.hour <= 4 THEN 'night'
  END                                                                                            AS day_part

, CASE
    WHEN tim.hour >= 5 AND tim.hour <= 11 THEN 1
    WHEN tim.hour >= 12 AND tim.hour <= 16 THEN 2
    WHEN tim.hour >= 17 AND tim.hour <= 20 THEN 3
    WHEN tim.hour >= 21 THEN 4
    WHEN tim.hour <= 4 THEN 4
  END                                                                                            AS day_part_sort

, CASE
    WHEN tim.hour >= 5 AND tim.hour <= 8 THEN 'morning (early)'
    WHEN tim.hour >= 9 AND tim.hour <= 10 THEN 'morning'
    WHEN tim.hour >= 11 AND tim.hour <= 11 THEN 'morning (late)'
    WHEN tim.hour >= 12 AND tim.hour <= 15 THEN 'afternoon (early)'
    WHEN tim.hour >= 16 AND tim.hour <= 16 THEN 'afternoon (late)'
    WHEN tim.hour >= 17 AND tim.hour <= 18 THEN 'evening (vroeg)'
    WHEN tim.hour >= 19 AND tim.hour <= 20 THEN 'evening'
    WHEN tim.hour >= 21 THEN 'night'
    WHEN tim.hour <= 4 THEN 'night'
  END                                                                                            AS day_part_alt

, CASE
    WHEN tim.hour >= 5 AND tim.hour <= 8 THEN 1
    WHEN tim.hour >= 9 AND tim.hour <= 10 THEN 2
    WHEN tim.hour >= 11 AND tim.hour <= 11 THEN 3
    WHEN tim.hour >= 12 AND tim.hour <= 15 THEN 4
    WHEN tim.hour >= 16 AND tim.hour <= 16 THEN 5
    WHEN tim.hour >= 17 AND tim.hour <= 18 THEN 6
    WHEN tim.hour >= 19 AND tim.hour <= 20 THEN 7
    WHEN tim.hour >= 21 THEN 8
    WHEN tim.hour <= 4 THEN 8
  END                                                                                            AS day_part_alt_sort

FROM
  cte_times AS tim
