/*
    The ISO 8601 week-numbering year of a date (the year its ISO week belongs to). Snowflake and
    DuckDB spell the date part differently, hence the dispatch.
*/

{% macro iso_year(date) -%}
{{ return(adapter.dispatch('iso_year', 'dbt_common')(date)) }}
{%- endmacro %}

{% macro snowflake__iso_year(date) -%}
DATE_PART('yearofweekiso', {{ date }})
{%- endmacro %}

{% macro duckdb__iso_year(date) -%}
DATE_PART('isoyear', {{ date }})
{%- endmacro %}
