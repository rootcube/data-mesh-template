/*
    UTC "now" as TIMESTAMP_NTZ, independent of the session/user TIMEZONE.
    SYSDATE() always returns UTC and ignores the TIMEZONE parameter, unlike
    CURRENT_TIMESTAMP()/LOCALTIMESTAMP() which return the session timezone. Use
    this instead of CURRENT_TIMESTAMP so results never depend on connection
    settings and match the platform's UTC-NTZ timestamp convention. The local
    DuckDB target has no SYSDATE(), hence the dispatch.
*/

{% macro utc_now() -%}
{{ return(adapter.dispatch('utc_now', 'dbt_common')()) }}
{%- endmacro %}

{% macro snowflake__utc_now() -%}
SYSDATE()
{%- endmacro %}

{% macro duckdb__utc_now() -%}
CAST(NOW() AT TIME ZONE 'UTC' AS TIMESTAMP)
{%- endmacro %}
