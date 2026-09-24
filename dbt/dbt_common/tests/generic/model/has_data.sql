{% test has_data(model) %}

    {{ config(store_failures=false) }}

    -- NOT EXISTS short-circuits on the first row instead of counting every row.
    -- store_failures off: the failure row is a constant 1, so a per-build failures table is pure churn.
    SELECT 1 AS validation_error
    WHERE NOT EXISTS (SELECT 1 FROM {{ model }})

{% endtest %}
