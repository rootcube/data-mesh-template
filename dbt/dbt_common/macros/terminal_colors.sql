/*{#
    Returns a dict of ANSI terminal color codes.
    Set dbt var `terminal_colors: false` to disable (e.g. for dbt Fusion, which cannot render ANSI escapes).
    Set dbt var `terminal_colors: true` to enable (e.g. for dbt core).
#}*/

{% macro terminal_colors() %}
  {% set enabled = var('terminal_colors', false) %}
  {% if enabled %}
    {{ return({
      'cyan':   '\x1b[36m',
      'bold':   '\x1b[1;36m',
      'dim':    '\x1b[2;36m',
      'link':   '\x1b[4;36m',
      'green':  '\x1b[32m',
      'red':    '\x1b[31m',
      'yellow': '\x1b[33m',
      'reset':  '\x1b[0m',
    }) }}
  {% else %}
    {{ return({
      'cyan':   '',
      'bold':   '',
      'dim':    '',
      'link':   '',
      'green':  '',
      'red':    '',
      'yellow': '',
      'reset':  '',
    }) }}
  {% endif %}
{% endmacro %}
