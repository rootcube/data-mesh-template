/*
    Refreshes the directory table of the dlt load stage at the start of a run: ST_DEFAULT in the source layer,
    `_SRC.ST_DEFAULT`, or your personal `<SNOWFLAKE_SCHEMA>_SRC.ST_DEFAULT` in dev (terraform/stages.tf).
    Internal stages never refresh it by themselves, so dbt does it before reading the source layer.
*/

{% macro refresh_stages() %}

  {% if not execute or flags.WHICH not in ['run', 'build'] or target.name | trim | lower == 'dummy' %}
    {{ return('') }}
  {% endif %}

  {% set stage = target.database ~ '.' ~ (dbt_common.generate_schema_name('src', none) | trim) ~ '.ST_DEFAULT' %}
  {% do run_query('ALTER STAGE ' ~ stage ~ ' REFRESH') %}
  {{ log('Refreshed the directory table of ' ~ stage, info=true) }}

{% endmacro %}
