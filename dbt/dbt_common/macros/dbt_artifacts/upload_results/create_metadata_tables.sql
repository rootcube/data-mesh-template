{#
    LOCAL ADDITION - not part of vendored dbt_artifacts upstream.

    Makes the upload path self-sufficient: `upload_results` writes into the
    `pre__dbt__*` tables resolved by `dbt_common.get_relation`, but upstream
    dbt_artifacts never ships DDL for them (it assumes a monitoring project has already
    built them as models). Any project that only calls `dbt_common.upload_results(results)`
    from its `on-run-end` hook would fail on a fresh database where nothing has created
    those tables yet. This macro creates the MTD schema and the tables on demand, so the
    upload works standalone. A monitoring project can consume them as dbt *sources*.
    The tables live in the metadata layer (`_MTD`, or `<prefix>_MTD` in dev).

    Column definitions (names, order, types) are hand-derived from the upstream v2.10.0
    model shells (`models/sources/*.sql`) for the Snowflake path only:
        type_string()    -> VARCHAR
        type_timestamp() -> TIMESTAMP
        type_int()       -> INTEGER
        type_float()     -> FLOAT
        type_boolean()   -> BOOLEAN
        type_json()      -> OBJECT
        type_array()     -> ARRAY
    Names and order were cross-checked against `get_column_name_list` in
    `get_column_name_lists.sql` for every dataset; there were no mismatches.

    Schema evolution is MANUAL: `create table if not exists` never alters an existing
    table. If a future upstream sync changes a dataset's columns, both this file and
    `get_column_name_lists.sql` must be updated, and any already-created tables in every
    environment must be ALTERed by hand to match.
#}

{% macro create_metadata_tables_if_not_exist() %}

    {% if execute %}

        {# Personal schemas are created on demand in dev; the shared _MTD is provisioned by Terraform. #}
        {% set metadata_schema = dbt_common.generate_schema_name('mtd', none) | trim %}
        {% if target.name | trim | lower == 'dev' %}
            {% do run_query("CREATE SCHEMA IF NOT EXISTS " ~ target.database ~ "." ~ metadata_schema) %}
        {% endif %}

        {% set ddl_by_dataset = {
            'exposures': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                name VARCHAR,
                type VARCHAR,
                owner OBJECT,
                maturity VARCHAR,
                path VARCHAR,
                description VARCHAR,
                url VARCHAR,
                package_name VARCHAR,
                depends_on_nodes ARRAY,
                tags ARRAY,
                all_results OBJECT
            ',
            'invocations': '
                command_invocation_id VARCHAR,
                dbt_version VARCHAR,
                project_name VARCHAR,
                run_started_at TIMESTAMP,
                dbt_command VARCHAR,
                full_refresh_flag BOOLEAN,
                target_profile_name VARCHAR,
                target_name VARCHAR,
                target_schema VARCHAR,
                target_threads INTEGER,
                dbt_cloud_project_id VARCHAR,
                dbt_cloud_job_id VARCHAR,
                dbt_cloud_run_id VARCHAR,
                dbt_cloud_run_reason_category VARCHAR,
                dbt_cloud_run_reason VARCHAR,
                env_vars OBJECT,
                dbt_vars OBJECT,
                invocation_args OBJECT,
                dbt_custom_envs OBJECT
            ',
            'model_executions': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                was_full_refresh BOOLEAN,
                thread_id VARCHAR,
                status VARCHAR,
                compile_started_at TIMESTAMP,
                query_completed_at TIMESTAMP,
                total_node_runtime FLOAT,
                rows_affected INTEGER,
                materialization VARCHAR,
                schema VARCHAR,
                name VARCHAR,
                alias VARCHAR,
                message VARCHAR,
                adapter_response OBJECT
            ',
            'models': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                database VARCHAR,
                schema VARCHAR,
                name VARCHAR,
                depends_on_nodes ARRAY,
                package_name VARCHAR,
                path VARCHAR,
                checksum VARCHAR,
                materialization VARCHAR,
                tags ARRAY,
                meta OBJECT,
                alias VARCHAR,
                all_results OBJECT
            ',
            'seed_executions': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                was_full_refresh BOOLEAN,
                thread_id VARCHAR,
                status VARCHAR,
                compile_started_at TIMESTAMP,
                query_completed_at TIMESTAMP,
                total_node_runtime FLOAT,
                rows_affected INTEGER,
                materialization VARCHAR,
                schema VARCHAR,
                name VARCHAR,
                alias VARCHAR,
                message VARCHAR,
                adapter_response OBJECT
            ',
            'seeds': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                database VARCHAR,
                schema VARCHAR,
                name VARCHAR,
                package_name VARCHAR,
                path VARCHAR,
                checksum VARCHAR,
                meta OBJECT,
                alias VARCHAR,
                all_results OBJECT
            ',
            'snapshot_executions': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                was_full_refresh BOOLEAN,
                thread_id VARCHAR,
                status VARCHAR,
                compile_started_at TIMESTAMP,
                query_completed_at TIMESTAMP,
                total_node_runtime FLOAT,
                rows_affected INTEGER,
                materialization VARCHAR,
                schema VARCHAR,
                name VARCHAR,
                alias VARCHAR,
                message VARCHAR,
                adapter_response OBJECT
            ',
            'snapshots': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                database VARCHAR,
                schema VARCHAR,
                name VARCHAR,
                depends_on_nodes ARRAY,
                package_name VARCHAR,
                path VARCHAR,
                checksum VARCHAR,
                strategy VARCHAR,
                meta OBJECT,
                alias VARCHAR,
                all_results OBJECT
            ',
            'sources': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                database VARCHAR,
                schema VARCHAR,
                source_name VARCHAR,
                loader VARCHAR,
                name VARCHAR,
                identifier VARCHAR,
                loaded_at_field VARCHAR,
                freshness ARRAY,
                all_results OBJECT
            ',
            'source_freshness': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                status VARCHAR,
                max_loaded_at TIMESTAMP,
                snapshotted_at TIMESTAMP,
                age_seconds FLOAT,
                execution_seconds FLOAT,
                thread_id VARCHAR
            ',
            'test_executions': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                was_full_refresh BOOLEAN,
                thread_id VARCHAR,
                status VARCHAR,
                compile_started_at TIMESTAMP,
                query_completed_at TIMESTAMP,
                total_node_runtime FLOAT,
                rows_affected INTEGER,
                failures INTEGER,
                message VARCHAR,
                adapter_response OBJECT
            ',
            'tests': '
                command_invocation_id VARCHAR,
                node_id VARCHAR,
                run_started_at TIMESTAMP,
                name VARCHAR,
                depends_on_nodes ARRAY,
                package_name VARCHAR,
                test_path VARCHAR,
                tags ARRAY,
                all_results OBJECT
            ',
        } %}

        {% for dataset, column_ddl in ddl_by_dataset.items() %}
            {% set relation = dbt_common.get_relation(dataset) %}
            {% do run_query('create table if not exists ' ~ relation ~ ' (' ~ column_ddl ~ ')') %}
        {% endfor %}

    {% endif %}

{% endmacro %}
