/*{#
    Logs a run summary at the end of each dbt invocation.
    Shows totals by status, slowest models, failed tests, and total runtime.

    Usage (in on-run-end):
      - "{{ dbt_common.log_run_summary(results) }}"
#}*/

{% macro log_run_summary(results) %}

  {% if not execute %}
    {{ return('') }}
  {% endif %}

  {% set c       = dbt_common.terminal_colors() %}
  {% set cyan    = c.cyan %}
  {% set bold    = c.bold %}
  {% set dim     = c.dim %}
  {% set green   = c.green %}
  {% set red     = c.red %}
  {% set yellow  = c.yellow %}
  {% set reset   = c.reset %}
  {% set divider = dim ~ '─' * 80 ~ reset %}

  {# Categorize results #}
  {% set models_pass = [] %}
  {% set models_fail = [] %}
  {% set models_skip = [] %}
  {% set tests_pass  = [] %}
  {% set tests_fail  = [] %}
  {% set tests_warn  = [] %}
  {% set tests_skip  = [] %}
  {% set seeds_pass  = [] %}
  {% set total_time  = [0.0] %}

  {% for res in results %}
    {% if res.execution_time %}
      {% do total_time.append(total_time.pop() + res.execution_time) %}
    {% endif %}

    {% if res.node.resource_type == 'model' %}
      {% if res.status == 'success' %}
        {% do models_pass.append(res) %}
      {% elif res.status == 'error' %}
        {% do models_fail.append(res) %}
      {% else %}
        {% do models_skip.append(res) %}
      {% endif %}

    {% elif res.node.resource_type == 'test' %}
      {% if res.status == 'pass' %}
        {% do tests_pass.append(res) %}
      {% elif res.status == 'fail' or res.status == 'error' %}
        {% do tests_fail.append(res) %}
      {% elif res.status == 'warn' %}
        {% do tests_warn.append(res) %}
      {% else %}
        {% do tests_skip.append(res) %}
      {% endif %}

    {% elif res.node.resource_type == 'seed' %}
      {% if res.status == 'success' %}
        {% do seeds_pass.append(res) %}
      {% endif %}
    {% endif %}
  {% endfor %}

  {# Round once, then split: rounding the remainder alone can print "3m 60.0s". #}
  {% set total_seconds = total_time[0] | round(1) %}
  {% set minutes = (total_seconds // 60) | int %}
  {% set seconds = (total_seconds - minutes * 60) | round(1) %}

  {{ log('', info=true) }}
  {{ log(divider, info=true) }}
  {{ log(bold ~ '  RUN SUMMARY' ~ reset, info=true) }}
  {{ log(divider, info=true) }}
  {{ log(cyan ~ '  Invocation ID:  ' ~ bold ~ invocation_id ~ reset, info=true) }}
  {{ log(cyan ~ '  Total runtime:  ' ~ bold ~ minutes ~ 'm ' ~ seconds ~ 's' ~ reset, info=true) }}
  {{ log(divider, info=true) }}

  {# Models summary #}
  {% set model_total = models_pass | length + models_fail | length + models_skip | length %}
  {% if model_total > 0 %}
    {{ log(cyan ~ '  Models:         '
      ~ green ~ (models_pass | length) ~ ' passed' ~ reset ~ '  '
      ~ (red ~ (models_fail | length) ~ ' failed' ~ reset ~ '  ' if models_fail | length > 0 else '')
      ~ (yellow ~ (models_skip | length) ~ ' skipped' ~ reset if models_skip | length > 0 else '')
    , info=true) }}
  {% endif %}

  {# Tests summary #}
  {% set test_total = tests_pass | length + tests_fail | length + tests_warn | length + tests_skip | length %}
  {% if test_total > 0 %}
    {{ log(cyan ~ '  Tests:          '
      ~ green ~ (tests_pass | length) ~ ' passed' ~ reset ~ '  '
      ~ (red ~ (tests_fail | length) ~ ' failed' ~ reset ~ '  ' if tests_fail | length > 0 else '')
      ~ (yellow ~ (tests_warn | length) ~ ' warned' ~ reset ~ '  ' if tests_warn | length > 0 else '')
      ~ (dim ~ (tests_skip | length) ~ ' skipped' ~ reset if tests_skip | length > 0 else '')
    , info=true) }}
  {% endif %}

  {# Seeds summary #}
  {% if seeds_pass | length > 0 %}
    {{ log(cyan ~ '  Seeds:          ' ~ green ~ (seeds_pass | length) ~ ' loaded' ~ reset, info=true) }}
  {% endif %}

  {# Failed tests detail #}
  {% if tests_fail | length > 0 %}
    {{ log(divider, info=true) }}
    {{ log(red ~ '  Failed tests:' ~ reset, info=true) }}
    {% for res in tests_fail %}
      {{ log(red ~ '    ✗ ' ~ reset ~ res.node.name ~ dim ~ ' — ' ~ res.message ~ reset, info=true) }}
    {% endfor %}
  {% endif %}

  {# Warned tests detail #}
  {% if tests_warn | length > 0 %}
    {{ log(divider, info=true) }}
    {{ log(yellow ~ '  Warned tests:' ~ reset, info=true) }}
    {% for res in tests_warn %}
      {{ log(yellow ~ '    ⚠ ' ~ reset ~ res.node.name ~ dim ~ ' — ' ~ res.message ~ reset, info=true) }}
    {% endfor %}
  {% endif %}

  {# Failed models detail #}
  {% if models_fail | length > 0 %}
    {{ log(divider, info=true) }}
    {{ log(red ~ '  Failed models:' ~ reset, info=true) }}
    {% for res in models_fail %}
      {{ log(red ~ '    ✗ ' ~ reset ~ res.node.name ~ dim ~ ' — ' ~ res.message ~ reset, info=true) }}
    {% endfor %}
  {% endif %}

  {# Slowest models (top 5) #}
  {% if models_pass | length > 0 %}
    {% set sorted_models = models_pass | sort(attribute='execution_time', reverse=true) %}
    {{ log(divider, info=true) }}
    {{ log(cyan ~ '  Slowest models:' ~ reset, info=true) }}
    {% for res in sorted_models[:5] %}
      {% set dur = res.execution_time | round(1) %}
      {{ log(cyan ~ '    ' ~ bold ~ dur ~ 's' ~ reset ~ '  ' ~ res.node.name, info=true) }}
    {% endfor %}
  {% endif %}
  {{ log(divider, info=true) }}
  {{ log('', info=true) }}

{% endmacro %}
