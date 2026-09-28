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
, CAST(DATEADD('day', DAY, '1900-01-01') AS DATE)     AS date
, CAST(DATEADD('day', DAY, '1900-01-01') AS DATETIME) AS date_time

-- One row per day from {{ first_date }} to {{ last_date }}: the generator is sized to the window,
-- so nothing needs filtering. ROW_NUMBER over SEQ4 because SEQ4 alone may skip values. `day` is
-- the offset from 1900-01-01 (uppercase DAY because sqlfluff reads the second DATEADD argument
-- as a date part).
FROM
  (SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 + {{ first_day }} AS day FROM TABLE(GENERATOR(ROWCOUNT => {{ day_count }})))
