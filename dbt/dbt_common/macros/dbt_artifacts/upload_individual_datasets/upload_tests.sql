{% macro upload_tests(tests) -%}
    {{ return(adapter.dispatch("get_tests_dml_sql", "dbt_common")(tests)) }}
{%- endmacro %}

{% macro default__get_tests_dml_sql(tests) -%}

    {% if tests != [] %}
        {% set test_values %}
        select
            {{ adapter.dispatch('column_identifier', 'dbt_common')(1) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(2) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(3) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(4) }},
            {{ adapter.dispatch('parse_json', 'dbt_common')(adapter.dispatch('column_identifier', 'dbt_common')(5)) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(6) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(7) }},
            {{ adapter.dispatch('parse_json', 'dbt_common')(adapter.dispatch('column_identifier', 'dbt_common')(8)) }},
            {{ adapter.dispatch('parse_json', 'dbt_common')(adapter.dispatch('column_identifier', 'dbt_common')(9)) }}
        from values
        {% for test in tests -%}
            (
                '{{ invocation_id }}', {# command_invocation_id #}
                '{{ test.unique_id }}', {# node_id #}
                '{{ run_started_at }}', {# run_started_at #}
                '{{ test.name }}', {# name #}
                '{{ tojson(test.depends_on.nodes) }}', {# depends_on_nodes #}
                '{{ test.package_name }}', {# package_name #}
                '{{ test.original_file_path | replace('\\', '\\\\') }}', {# test_path #}
                '{{ tojson(test.tags) }}', {# tags #}
                {% if var('dbt_artifacts_exclude_all_results', false) %}
                    null
                {% else %}
                    '{{ tojson(test) | replace("\\", "\\\\") | replace("'","\\'") | replace('"', '\\"') }}' {# all_fields #}
                {% endif %}
            )
            {%- if not loop.last %},{%- endif %}
        {%- endfor %}
        {% endset %}
        {{ test_values }}
    {% else %} {{ return("") }}
    {% endif %}
{% endmacro -%}
