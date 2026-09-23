{% test rows_expected(model, value) %}

    SELECT 1 AS validation_error
    WHERE ( SELECT COUNT(*) FROM {{ model }} ) != {{ value }}

{% endtest %}
