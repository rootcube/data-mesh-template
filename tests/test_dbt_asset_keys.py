from orchestrator.locations.dbt.shared import compute_asset_key


def test_own_model_key_follows_the_file_path() -> None:
    node = {
        "package_name": "dbt_example",
        "original_file_path": "models/02_stg/knmi/stg__knmi__climate_hourly.sql",
        "name": "stg__knmi__climate_hourly",
    }
    assert compute_asset_key(node, "dbt_example").path == [
        "dbt_example",
        "models",
        "02_stg",
        "knmi",
        "stg__knmi__climate_hourly",
    ]


def test_windows_path_gives_the_same_key() -> None:
    node = {
        "package_name": "dbt_example",
        "original_file_path": "models\\02_stg\\knmi\\stg__knmi__climate_hourly.sql",
        "name": "stg__knmi__climate_hourly",
    }
    assert compute_asset_key(node, "dbt_example").path == [
        "dbt_example",
        "models",
        "02_stg",
        "knmi",
        "stg__knmi__climate_hourly",
    ]


def test_package_node_is_prefixed_with_the_package() -> None:
    node = {"package_name": "dbt_common", "original_file_path": "seeds/seed_month.csv", "name": "seed_month"}
    assert compute_asset_key(node, "dbt_example").path == [
        "dbt_example",
        "packages",
        "dbt_common",
        "seeds",
        "seed_month",
    ]


def test_meta_asset_key_wins() -> None:
    node = {
        "package_name": "dbt_example",
        "resource_type": "source",
        "source_name": "knmi",
        "name": "climate_hourly",
        "config": {"meta": {"dagster": {"asset_key": ["dlt", "ingest", "knmi", "climate_hourly"]}}},
    }
    assert compute_asset_key(node, "dbt_example").path == ["dlt", "ingest", "knmi", "climate_hourly"]
