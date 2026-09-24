/*{# Refreshes the directory table of the dlt load stage (_SRC.ST_DLT, terraform/stages.tf) at the start of a run.
     Internal stages never refresh it by themselves, so dbt does it before reading the source layer. #}*/

{% macro refresh_stages() %}

  {% if not execute or flags.WHICH not in ['run', 'build'] or target.name | trim | lower == 'dummy' %}
    {{ return('') }}
  {% endif %}

  {% set stage = target.database ~ '._SRC.ST_DLT' %}
  {% do run_query('ALTER STAGE ' ~ stage ~ ' REFRESH') %}
  {{ log('Refreshed the directory table of ' ~ stage, info=true) }}

{% endmacro %}
