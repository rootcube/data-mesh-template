{# dbt doesn't like us ref'ing in an operation so we fetch the info from the graph #}

{% macro upload_results(results) -%}

    {% if execute %}

        {# LOCAL ADDITION: ensure the target tables exist before inserting into them #}
        {% do dbt_common.create_metadata_tables_if_not_exist() %}

        {# LOCAL ADDITION: freshness runs carry SourceFreshnessResults - upload those
           plus the invocation anchor, NOT the graph datasets (freshness runs hourly+;
           re-uploading node metadata every check would flood the metadata tables) #}
        {% if flags.WHICH == 'freshness' %}
            {% set datasets_to_load = ['source_freshness', 'invocations'] %}
        {% else %}
            {% set datasets_to_load = ['exposures', 'seeds', 'snapshots', 'invocations', 'sources', 'tests', 'models'] %}
            {% if results != [] %}
                {# When executing, and results are available, then upload the results #}
                {% set datasets_to_load = ['model_executions', 'seed_executions', 'test_executions', 'snapshot_executions'] + datasets_to_load %}
            {% endif %}
        {% endif %}

        {# Upload each data set in turn #}
        {% for dataset in datasets_to_load %}

            {% do log("Uploading " ~ dataset.replace("_", " "), true) %}

            {# Get the results that need to be uploaded #}
            {% set objects = dbt_common.get_dataset_content(dataset) %}

            {# Upload in chunks to reduce the query size #}
            {% if dataset == 'models' %}
                {% set upload_limit = 50 if target.type == 'bigquery' else 100 %}
            {% else %}
                {% set upload_limit = 300 if target.type == 'bigquery' else 5000 %}
            {% endif %}

            {# Loop through each chunk in turn #}
            {% for i in range(0, objects | length, upload_limit) -%}

                {# Get just the objects to load on this loop #}
                {% set content = dbt_common.get_table_content_values(dataset, objects[i: i + upload_limit]) %}

                {# Insert the content into the metadata table #}
                {{ dbt_common.insert_into_metadata_table(
                    dataset=dataset,
                    fields=dbt_common.get_column_name_list(dataset),
                    content=content
                    )
                }}

            {# Loop the next 'chunk' #}
            {% endfor %}

        {# Loop the next 'dataset' #}
        {% endfor %}

    {% endif %}

{%- endmacro %}
