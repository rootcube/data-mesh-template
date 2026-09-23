{{
    config(
        enabled=true,
        tags=['owner=public', 'system=generic', 'category=calendar']
    )
}}

SELECT
  cal.date_simple AS id_dim__generic__calendar

-- Dates
, cal.date
, cal.date_time
, cal.date_simple

-- Default Attributes
, cal.year_nr
, cal.base_year
, cal.quarter_nr
, cal.month_nr
, cal.month_name
, cal.week_nr
, cal.iso_year_nr
, cal.iso_week_nr

-- Holiday
, cal.is_holiday
, cal.holiday_name

-- Additional worst case day attributes
, cal.is_high_generation_day
, cal.is_high_consumption_day

FROM
  {{ ref('int__generic__calendar') }} AS cal
