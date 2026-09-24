/*{#
    Adds search optimization to a table for fast lookups.
    Safely skips views and ephemeral models.

    INPUTS:

    - target_relation (Relation): The target table relation (typically `this`).
    - operations (str): The search optimization operations to add.
                        Default: 'EQUALITY(*), SUBSTRING(*)' (all columns).

    USAGE:

    As a post_hook (per model or directory-level in dbt_project.yml):
        +post-hook:
          - "{{ search_optimization(this) }}"
          - "{{ search_optimization(this, 'EQUALITY(col_a), SUBSTRING(col_b)') }}"
#}*/

{% macro search_optimization(target_relation, operations='EQUALITY(*), SUBSTRING(*)') %}

    {% if config.get('materialized') in ['table', 'incremental'] %}
        ALTER TABLE {{ target_relation }} ADD SEARCH OPTIMIZATION ON {{ operations }}
    {% endif %}

{% endmacro %}
