/*
    A TIME from an hour, minute and second: Snowflake's TIME_FROM_PARTS, MAKE_TIME on the local
    DuckDB target.
*/

{% macro time_from_parts(hour, minute, second) -%}
{{ return(adapter.dispatch('time_from_parts', 'dbt_common')(hour, minute, second)) }}
{%- endmacro %}

{% macro snowflake__time_from_parts(hour, minute, second) -%}
TIME_FROM_PARTS({{ hour }}, {{ minute }}, {{ second }})
{%- endmacro %}

{% macro duckdb__time_from_parts(hour, minute, second) -%}
MAKE_TIME({{ hour }}, {{ minute }}, CAST({{ second }} AS DOUBLE))
{%- endmacro %}
