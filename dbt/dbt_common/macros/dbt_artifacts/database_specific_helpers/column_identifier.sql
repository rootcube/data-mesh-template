{% macro column_identifier(column_index) -%}
  {{ return(adapter.dispatch('column_identifier', 'dbt_common')(column_index)) }}
{%- endmacro %}

{% macro default__column_identifier(column_index) -%}
    {{ column_index }}
{%- endmacro %}

{% macro snowflake__column_identifier(column_index) -%}
    ${{ column_index }}
{%- endmacro %}
