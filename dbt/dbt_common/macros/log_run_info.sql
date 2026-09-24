/*{# Logs run context at the start of each dbt invocation. #}*/

{% macro log_run_info() %}

  {% if not execute %}
    {{ return('') }}
  {% endif %}

  {% set c       = dbt_common.terminal_colors() %}
  {% set cyan    = c.cyan %}
  {% set bold    = c.bold %}
  {% set link    = c.link %}
  {% set dim     = c.dim %}
  {% set reset   = c.reset %}
  {% set divider = dim ~ '─' * 80 ~ reset %}

  {% set sf_organization = run_query("SELECT LOWER(CURRENT_ORGANIZATION_NAME())").columns[0].values()[0] %}
  {% set sf_account = run_query("SELECT LOWER(CURRENT_ACCOUNT_NAME())").columns[0].values()[0] %}
  {% set sf_user = run_query("SELECT CURRENT_USER()").columns[0].values()[0] %}
  {% set sf_base_url = 'https://app.snowflake.com/' ~ sf_organization ~ '/' ~ sf_account %}
  {% set url_query = sf_base_url ~ '/#/compute/history/queries?query_tag=dbt_invocation_id:' ~ invocation_id ~ '&user=NAMED%3A' ~ sf_user %}
  {% set url_catalog = sf_base_url ~ '/#/data/databases/' ~ target.database %}

  {{ log('', info=true) }}
  {{ log(divider, info=true) }}
  {{ log(bold ~ '  RUN INFO' ~ reset, info=true) }}
  {{ log(divider, info=true) }}
  {{ log(cyan ~ '  Invocation ID : ' ~ bold ~ invocation_id ~ reset, info=true) }}
  {{ log(cyan ~ '  Target        : ' ~ bold ~ target.name ~ reset, info=true) }}
  {{ log(cyan ~ '  Organization  : ' ~ bold ~ sf_organization ~ reset, info=true) }}
  {{ log(cyan ~ '  Account       : ' ~ bold ~ sf_account ~ reset, info=true) }}
  {{ log(cyan ~ '  Database      : ' ~ bold ~ target.database ~ reset, info=true) }}
  {{ log(cyan ~ '  Warehouse     : ' ~ bold ~ target.warehouse ~ reset, info=true) }}
  {{ log(cyan ~ '  Threads       : ' ~ bold ~ target.threads ~ reset, info=true) }}
  {{ log(cyan ~ '  User          : ' ~ bold ~ sf_user ~ dim ~ ' [' ~ target.user ~ ']' ~ reset, info=true) }}
  {{ log(divider, info=true) }}
  {{ log(cyan ~ '  Catalog       : ' ~ link ~ url_catalog ~ reset, info=true) }}
  {{ log(cyan ~ '  Queries       : ' ~ link ~ url_query ~ reset, info=true) }}
  {{ log(divider, info=true) }}
  {{ log('', info=true) }}

{% endmacro %}
