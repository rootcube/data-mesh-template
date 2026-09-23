{#-
    LOCAL ADDITION - not part of vendored dbt_artifacts upstream.

    Uploads `dbt source freshness` results (SourceFreshnessResult objects): one row
    per checked source table per freshness invocation. Enables SLA/lag tracking per
    source in a monitoring project. Column order must match the
    'source_freshness' entries in get_column_name_lists.sql and
    create_metadata_tables.sql.

    Nullable fields: max_loaded_at/snapshotted_at/age are None on runtime errors.
-#}

{% macro upload_source_freshness(freshness_results) -%}
    {{ return(adapter.dispatch("get_source_freshness_dml_sql", "dbt_common")(freshness_results)) }}
{%- endmacro %}

{% macro default__get_source_freshness_dml_sql(freshness_results) -%}
    {% if freshness_results != [] %}
        {% set freshness_values %}
        select
            {{ adapter.dispatch('column_identifier', 'dbt_common')(1) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(2) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(3) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(4) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(5) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(6) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(7) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(8) }},
            {{ adapter.dispatch('column_identifier', 'dbt_common')(9) }}
        from values
        {% for result in freshness_results -%}
            (
                '{{ invocation_id }}', {# command_invocation_id #}
                '{{ result.node.unique_id }}', {# node_id #}
                '{{ run_started_at }}', {# run_started_at #}
                '{{ result.status }}', {# status #}
                {% if result.max_loaded_at %}'{{ result.max_loaded_at }}'{% else %}null{% endif %}, {# max_loaded_at #}
                {% if result.snapshotted_at %}'{{ result.snapshotted_at }}'{% else %}null{% endif %}, {# snapshotted_at #}
                {% if result.age is not none %}{{ result.age }}{% else %}null{% endif %}, {# age_seconds #}
                {% if result.execution_time is not none %}{{ result.execution_time }}{% else %}null{% endif %}, {# execution_seconds #}
                '{{ result.thread_id }}' {# thread_id #}
            )
            {%- if not loop.last %},{%- endif %}
        {% endfor %}
        {% endset %}
        {{ freshness_values }}
    {% else %}
        {{ return("") }}
    {% endif %}
{%- endmacro %}
