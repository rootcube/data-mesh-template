{#-
    Dispatch fallbacks for the Snowflake-only vendored macros. The `dummy` dbt target
    (profiles.yml) is an in-memory DuckDB used for parsing, compiling and linting without
    Snowflake credentials; dbt resolves `adapter.dispatch(...)` at that point and needs a
    default__ variant to exist. These delegate to the Snowflake implementation, which only
    renders SQL: the dummy target never executes the run-metadata upload.
-#}

{% macro default__get_model_executions_dml_sql(models) %}
    {{ return(dbt_common.snowflake__get_model_executions_dml_sql(models)) }}
{% endmacro %}

{% macro default__get_seed_executions_dml_sql(seeds) %}
    {{ return(dbt_common.snowflake__get_seed_executions_dml_sql(seeds)) }}
{% endmacro %}

{% macro default__get_snapshot_executions_dml_sql(snapshots) %}
    {{ return(dbt_common.snowflake__get_snapshot_executions_dml_sql(snapshots)) }}
{% endmacro %}

{% macro default__get_test_executions_dml_sql(tests) %}
    {{ return(dbt_common.snowflake__get_test_executions_dml_sql(tests)) }}
{% endmacro %}
