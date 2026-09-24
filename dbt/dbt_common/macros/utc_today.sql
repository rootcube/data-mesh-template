/*
    UTC "today" as DATE, independent of the session/user TIMEZONE. Use instead of
    CURRENT_DATE(), whose value depends on the session timezone near midnight. See
    utc_now for why SYSDATE() is timezone-safe.
*/

{% macro utc_today() -%}
CAST({{ dbt_common.utc_now() }} AS DATE)
{%- endmacro %}
