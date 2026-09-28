from dagster import AssetKey

from orchestrator.locations.dbt.shared import compute_asset_key, compute_group_name


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


def test_top_level_meta_asset_key_wins() -> None:
    node = {
        "package_name": "dbt_example",
        "resource_type": "source",
        "source_name": "knmi",
        "name": "climate_hourly",
        "meta": {"dagster": {"asset_key": ["dlt", "ingest", "knmi", "climate_hourly"]}},
    }
    assert compute_asset_key(node, "dbt_example").path == ["dlt", "ingest", "knmi", "climate_hourly"]


def test_group_is_the_key_without_its_last_segment() -> None:
    key = AssetKey(["dbt_example", "models", "02_stg", "knmi", "stg__knmi__climate_hourly"])
    assert compute_group_name(key) == "dbt_example/models/02_stg/knmi"


def test_group_of_a_package_key_keeps_the_package_prefix() -> None:
    key = AssetKey(["dbt_example", "packages", "dbt_common", "seeds", "seed_month"])
    assert compute_group_name(key) == "dbt_example/packages/dbt_common/seeds"


def test_group_of_a_one_segment_override_is_not_empty() -> None:
    # Dagster rejects an empty group name, so a single-element meta.dagster.asset_key
    # groups under itself instead of breaking the whole code location.
    assert compute_group_name(AssetKey(["climate_hourly"])) == "climate_hourly"
