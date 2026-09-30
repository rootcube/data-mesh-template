/*
    Refreshes the directory table of the dlt load stage at the start of a run: ST_DEFAULT in the source layer,
    `_SRC.ST_DEFAULT`, or your personal `<SNOWFLAKE_SCHEMA>_SRC.ST_DEFAULT` in dev (terraform/components/snowflake-project/stages.tf).
    Internal stages never refresh it by themselves, so dbt does it before reading the source layer.
*/

{% macro refresh_stages() %}

  {% if not execute or flags.WHICH not in ['run', 'build'] or target.type != 'snowflake' %}
    {{ return('') }}
  {% endif %}

  {% set schema = target.database ~ '.' ~ (dbt_common.generate_schema_name('src', none) | trim) %}
  {% set stage = schema ~ '.ST_DEFAULT' %}

  {# No stage yet, or no privileges on it: warn and let the run continue instead of aborting it. #}
  {% set found = run_query("SHOW STAGES LIKE 'ST_DEFAULT' IN SCHEMA " ~ schema) %}
  {% if found | length == 0 %}
    {{ log('Skipped the directory table refresh: ' ~ stage ~ ' does not exist or is not authorized. `just tf apply --all` provisions it (terraform/components/snowflake-project/stages.tf).', info=true) }}
    {{ return('') }}
  {% endif %}

  {% do run_query('ALTER STAGE ' ~ stage ~ ' REFRESH') %}
  {{ log('Refreshed the directory table of ' ~ stage, info=true) }}

{% endmacro %}
