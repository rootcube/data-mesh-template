/*
    The ISO 8601 week number of a date, independent of the session's week policy. Snowflake and
    DuckDB spell the date part differently, hence the dispatch.
*/

{% macro iso_week(date) -%}
{{ return(adapter.dispatch('iso_week', 'dbt_common')(date)) }}
{%- endmacro %}

{% macro snowflake__iso_week(date) -%}
DATE_PART('weekiso', {{ date }})
{%- endmacro %}

{% macro duckdb__iso_week(date) -%}
DATE_PART('week', {{ date }})
{%- endmacro %}
