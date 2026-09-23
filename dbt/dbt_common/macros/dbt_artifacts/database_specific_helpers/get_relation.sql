{#
    Vendored replacement for dbt_artifacts' graph-based get_relation.

    Resolves the raw upload tables by convention instead of graph lookup, so
    projects that only upload (via the dbt_common on-run-end hook) don't need
    the table models in their own graph. The physical tables live in the metadata
    layer (_MTD) of the project database and are created on demand (dev) by
    `dbt_common.create_metadata_tables_if_not_exist()` in the upload path itself.
    A monitoring project can consume them as dbt sources; nothing builds them as models.
#}

{% macro get_relation(relation_name) %}
    {% if execute %}
        {% set identifiers = {
            'exposures': 'pre__dbt__exposure',
            'invocations': 'pre__dbt__invocation',
            'model_executions': 'pre__dbt__model_execution',
            'models': 'pre__dbt__model',
            'seed_executions': 'pre__dbt__seed_execution',
            'seeds': 'pre__dbt__seed',
            'snapshot_executions': 'pre__dbt__snapshot_execution',
            'snapshots': 'pre__dbt__snapshot',
            'source_freshness': 'pre__dbt__source_freshness',
            'sources': 'pre__dbt__source',
            'test_executions': 'pre__dbt__test_execution',
            'tests': 'pre__dbt__test',
        } %}
        {% set relation = api.Relation.create(
            database=target.database,
            schema=dbt_common.generate_schema_name('mtd', none) | trim,
            identifier=identifiers[relation_name]
        ) %}
        {{ return(relation) }}
    {% endif %}
{% endmacro %}
