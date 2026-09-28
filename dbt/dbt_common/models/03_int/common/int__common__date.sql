{{
    config(
        enabled=true,
        materialized='table',
        tags=['owner=public', 'system=common', 'category=date'],
        unique_key=['date']
    )
}}

{#- The window this model covers: a fixed first year plus a horizon of years past the current one.
    Both are meta configs of the installing project (dbt_project.yml), the same route as the
    holiday country. The first year is a literal on purpose: a start that slides with the clock
    drops its oldest year the first time the model rebuilds in a new year, silently. -#}
{%- set model_meta = config.get('meta') or {} -%}
{%- set start_year = model_meta.get('calendar_start_year', 2000) | int -%}
{%- set horizon_years = model_meta.get('calendar_horizon_years', 10) | int -%}
{%- set epoch = modules.datetime.date(1900, 1, 1) -%}
{%- set first_date = modules.datetime.date(start_year, 1, 1) -%}
{%- set last_date = modules.datetime.date(modules.datetime.date.today().year + horizon_years, 12, 31) -%}
{%- set first_day = (first_date - epoch).days -%}
{%- set day_count = (last_date - first_date).days + 1 -%}

SELECT
  day
, CAST({{ dbt.dateadd('day', 'day', "CAST('1900-01-01' AS DATE)") }} AS DATE)     AS date
, CAST({{ dbt.dateadd('day', 'day', "CAST('1900-01-01' AS DATE)") }} AS DATETIME) AS date_time

-- One row per day from {{ first_date }} to {{ last_date }}: the integer series is sized to the
-- window, so nothing needs filtering. `day` is the offset from 1900-01-01.
FROM
  (SELECT n + {{ first_day }} AS day FROM {{ dbt_common.integer_series(day_count) }})
