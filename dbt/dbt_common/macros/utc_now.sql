/*
    UTC "now" as TIMESTAMP_NTZ, independent of the session/user TIMEZONE.
    SYSDATE() always returns UTC and ignores the TIMEZONE parameter, unlike
    CURRENT_TIMESTAMP()/LOCALTIMESTAMP() which return the session timezone. Use
    this instead of CURRENT_TIMESTAMP so results never depend on connection
    settings and match the platform's UTC-NTZ timestamp convention.
*/

{% macro utc_now() -%}
SYSDATE()
{%- endmacro %}
