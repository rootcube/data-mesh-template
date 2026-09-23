{% macro upload_seed_executions(seeds) -%}
    {{ return(adapter.dispatch("get_seed_executions_dml_sql", "dbt_common")(seeds)) }}
{%- endmacro %}

{% macro snowflake__get_seed_executions_dml_sql(seeds) -%}
    {% if seeds != [] %}
        {% set seed_execution_values %}
        select
            {{ adapter.dispatch('column_identifier', 'dbt_common')(1) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(2) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(3) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(4) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(5) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(6) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(7) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(8) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(9) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(10) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(11) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(12) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(13) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(14) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(15) }},
            {{ adapter.dispatch('parse_json', 'dbt_common')(adapter.dispatch('column_identifier', 'dbt_common')(16)) }}
        from values
        {% for model in seeds -%}
            (
                '{{ invocation_id }}', {# command_invocation_id #}
                '{{ model.node.unique_id }}', {# node_id #}
                '{{ run_started_at }}', {# run_started_at #}

                {% set config_full_refresh = model.node.config.full_refresh %}
                {% if config_full_refresh is none %}
                    {% set config_full_refresh = flags.FULL_REFRESH %}
                {% endif %}
                '{{ config_full_refresh }}', {# was_full_refresh #}

                '{{ model.thread_id }}', {# thread_id #}
                '{{ model.status }}', {# status #}

                {% set compile_started_at = (model.timing | selectattr("name", "eq", "compile") | first | default({}))["started_at"] %}
                {% if compile_started_at %}'{{ compile_started_at }}'{% else %}null{% endif %}, {# compile_started_at #}
                {% set query_completed_at = (model.timing | selectattr("name", "eq", "execute") | first | default({}))["completed_at"] %}
                {% if query_completed_at %}'{{ query_completed_at }}'{% else %}null{% endif %}, {# query_completed_at #}

                {{ model.execution_time }}, {# total_node_runtime #}
                try_cast('{{ model.adapter_response.rows_affected }}' as int), {# rows_affected #}
                '{{ model.node.config.materialized }}', {# materialization #}
                '{{ model.node.schema }}', {# schema #}
                '{{ model.node.name }}', {# name #}
                '{{ model.node.alias }}', {# alias #}
                '{{ model.message | replace("\\", "\\\\") | replace("'", "\\'") | replace('"', '\\"') }}', {# message #}
                '{{ tojson(model.adapter_response) | replace("\\", "\\\\") | replace("'", "\\'") | replace('"', '\\"') }}' {# adapter_response #}
            )
            {%- if not loop.last %},{%- endif %}
        {%- endfor %}
        {% endset %}
        {{ seed_execution_values }}
    {% else %} {{ return("") }}
    {% endif %}
{% endmacro -%}
