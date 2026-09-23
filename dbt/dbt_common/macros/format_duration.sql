{% macro format_duration(seconds) %}
{#- Seconds to an 'HH:MM:SS' display string; hours grow past 24 (e.g. 26:10:05). -#}
IFF(
    {{ seconds }} IS NULL
, NULL
, LPAD(CAST(CAST(FLOOR({{ seconds }} / 3600) AS INTEGER) AS VARCHAR), 2, '0')
  || ':' || LPAD(CAST(CAST(FLOOR(MOD({{ seconds }}, 3600) / 60) AS INTEGER) AS VARCHAR), 2, '0')
  || ':' || LPAD(CAST(CAST(FLOOR(MOD({{ seconds }}, 60)) AS INTEGER) AS VARCHAR), 2, '0')
)
{%- endmacro %}
