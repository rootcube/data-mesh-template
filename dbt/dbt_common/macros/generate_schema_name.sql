/*{#
    Schema naming for every project that installs dbt_common.

    Layers map to schemas of the project database DB_<PROJECT>_<ENV>. In the shared environments
    (tst, acc, prd) a layer's schema is `_<LAYER>`, provisioned by Terraform. In development
    every engineer works in personal schemas: `<target.schema>_<LAYER>`, created on demand,
    so several people share one development database without stepping on each other.

    | target  | target.schema | +schema | Result        |
    |---------|---------------|---------|---------------|
    | dev     | DBT_INFO      | stg     | DBT_INFO_STG  |
    | dev     | DBT_INFO      | (none)  | DBT_INFO      |
    | prd     | _TMP          | stg     | _STG          |
    | prd     | _TMP          | (none)  | _TMP          |

    To use it, a consuming project lists dbt_common in its dispatch search order:

        dispatch:
          - macro_namespace: dbt
            search_order: ["dbt_common", "dbt"]
#}*/

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set personal = target.name | trim | lower in ['dev', 'dummy'] -%}

    {%- if custom_schema_name is none -%}
        {{ target.schema | trim | upper }}
    {%- elif personal -%}
        {{ target.schema | trim | upper }}_{{ custom_schema_name | trim | upper }}
    {%- else -%}
        _{{ custom_schema_name | trim | upper }}
    {%- endif -%}

{%- endmacro %}


/*{# Dispatch entry point, picked up by `adapter.dispatch('generate_schema_name', 'dbt')` when
   `dbt_common` is in the consuming project's dispatch search_order. Delegates to the public
   macro above so user code can also call `dbt_common.generate_schema_name(...)` directly. #}*/
{% macro default__generate_schema_name(custom_schema_name, node) -%}
  {{ return(dbt_common.generate_schema_name(custom_schema_name, node)) }}
{%- endmacro %}
