{{
    config(
        enabled=true,
        tags=['owner=public', 'system=common', 'category=time']
    )
}}

SELECT
  time_simple AS id_dim__common__time

, time
, time_simple
, time_hour
, time_minute
, time_second

, hour_nr
, hour_code
, hour_name
, hour_sort

, minute_nr
, minute_code
, minute_name
, minute_sort

, second_nr
, second_code
, second_name
, second_sort

, day_part
, day_part_sort
, day_part_alt
, day_part_alt_sort

FROM
  {{ ref('int__common__time') }}
