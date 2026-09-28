/*
    A time or timestamp as the integer HHMMSS, the key of dim__common__time. Plain date parts, so
    it renders the same on Snowflake and the local DuckDB target.
*/

{% macro time_simple(timestamp) -%}
CAST(DATE_PART('hour', {{ timestamp }}) * 10000 + DATE_PART('minute', {{ timestamp }}) * 100 + DATE_PART('second', {{ timestamp }}) AS INTEGER)
{%- endmacro %}
