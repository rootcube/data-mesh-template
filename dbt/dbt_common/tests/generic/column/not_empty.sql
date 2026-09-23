{% test not_empty(model, column_name) %}
    SELECT *
    FROM {{ model }}
    WHERE COALESCE(CAST({{ column_name }} AS VARCHAR), '') = ''
{% endtest %}
