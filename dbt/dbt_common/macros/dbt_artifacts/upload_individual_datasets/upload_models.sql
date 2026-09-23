{% macro upload_models(models) -%}
    {{ return(adapter.dispatch("get_models_dml_sql", "dbt_common")(models)) }}
{%- endmacro %}

{% macro default__get_models_dml_sql(models) -%}

    {% if models != [] %}
        {% set model_values %}
        select
            {{ adapter.dispatch('column_identifier', 'dbt_common')(1) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(2) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(3) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(4) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(5) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(6) }},
            {{ adapter.dispatch('parse_json', 'dbt_common')(adapter.dispatch('column_identifier', 'dbt_common')(7)) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(8) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(9) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(10) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(11) }},
            {{ adapter.dispatch('parse_json', 'dbt_common')(adapter.dispatch('column_identifier', 'dbt_common')(12)) }},
            {{ adapter.dispatch('parse_json', 'dbt_common')(adapter.dispatch('column_identifier', 'dbt_common')(13)) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(14) }},
            {{ adapter.dispatch('parse_json', 'dbt_common')(adapter.dispatch('column_identifier', 'dbt_common')(15)) }}
        from values
        {% for model in models -%}
                {% set model_copy = dbt_common.safe_copy_mapping(model) -%}
            (
                '{{ invocation_id }}', {# command_invocation_id #}
                '{{ model_copy.unique_id }}', {# node_id #}
                '{{ run_started_at }}', {# run_started_at #}
                '{{ model_copy.database }}', {# database #}
                '{{ model_copy.schema }}', {# schema #}
                '{{ model_copy.name }}', {# name #}
                '{{ tojson(model_copy.depends_on.nodes) | replace('\\', '\\\\') }}', {# depends_on_nodes #}
                '{{ model_copy.package_name }}', {# package_name #}
                '{{ model_copy.original_file_path | replace('\\', '\\\\') }}', {# path #}
                '{{ model_copy.checksum.checksum  | replace('\\', '\\\\') }}', {# checksum #}
                '{{ model_copy.config.materialized }}', {# materialization #}
                '{{ tojson(model_copy.tags) }}', {# tags #}
                '{{ tojson(model_copy.config.meta) | replace("\\", "\\\\") | replace("'","\\'") | replace('"', '\\"') }}', {# meta #}
                '{{ model_copy.alias }}', {# alias #}
                {% if var('dbt_artifacts_exclude_all_results', false) %}
                    null
                {% else %}
                    '{{ tojson(model_copy) | replace("\\", "\\\\") | replace("'","\\'") | replace('"', '\\"') }}' {# all_results #}
                {% endif %}
            )
            {%- if not loop.last %},{%- endif %}
        {%- endfor %}
        {% endset %}
        {{ model_values }}
    {% else %} {{ return("") }}
    {% endif %}
{% endmacro -%}
