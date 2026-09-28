/*
    A date as the integer YYYYMMDD, the key of dim__common__calendar. Plain date parts, so it
    renders the same on Snowflake and the local DuckDB target.
*/

{% macro date_simple(date) -%}
CAST(DATE_PART('year', {{ date }}) * 10000 + DATE_PART('month', {{ date }}) * 100 + DATE_PART('day', {{ date }}) AS INTEGER)
{%- endmacro %}
