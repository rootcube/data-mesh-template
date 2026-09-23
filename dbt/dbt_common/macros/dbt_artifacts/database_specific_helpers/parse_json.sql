{% macro parse_json(field) -%}
  {{ return(adapter.dispatch('parse_json', 'dbt_common')(field)) }}
{%- endmacro %}

{% macro default__parse_json(field) -%}
    {{ field }}
{%- endmacro %}

{% macro snowflake__parse_json(field) -%}
    try_parse_json({{ field }})
{%- endmacro %}
