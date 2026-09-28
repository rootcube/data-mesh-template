/*
    A relation of `row_count` consecutive integers, 0 .. row_count - 1, in the column `n`: the
    row source of the date and time spines. Snowflake's GENERATOR is syntax, not a function,
    so this is dispatched per adapter; the local DuckDB target uses RANGE.
*/

{% macro integer_series(row_count) -%}
{{ return(adapter.dispatch('integer_series', 'dbt_common')(row_count)) }}
{%- endmacro %}

{% macro snowflake__integer_series(row_count) -%}
(SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS n FROM TABLE(GENERATOR(ROWCOUNT => {{ row_count }})))
{%- endmacro %}

{% macro duckdb__integer_series(row_count) -%}
(SELECT range AS n FROM RANGE({{ row_count }}))
{%- endmacro %}
