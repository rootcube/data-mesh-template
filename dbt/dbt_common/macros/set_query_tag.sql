/*{#
    Override dbt-snowflake's set_query_tag to always include the current invocation_id.
    This avoids partial parsing caching issues with {{ invocation_id }} in dbt_project.yml config.
#}*/

{% macro set_query_tag() -%}
    {% if not execute %}{{ return('') }}{% endif %}
    {% set query_tag = 'dbt_invocation_id:' ~ invocation_id %}
    {% set original_query_tag = get_current_query_tag() %}
    {% do run_query("alter session set query_tag = '{}'".format(query_tag)) %}
    {{ return(original_query_tag) }}
{%- endmacro %}


/*{# Dispatch entry point — picked up by `adapter.dispatch('set_query_tag', 'dbt')` when
   `dbt_common` is in the consuming project's dispatch search_order. Delegates to the public-API
   macro above so user code can keep calling `dbt_common.set_query_tag()` directly. #}*/
{% macro default__set_query_tag() -%}
  {{ return(dbt_common.set_query_tag()) }}
{%- endmacro %}
