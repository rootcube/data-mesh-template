from datetime import UTC, datetime

import pytest

from dlt_pipelines.__main__ import discover
from dlt_pipelines.pipelines.ingest.knmi.source import load_window
from dlt_pipelines.utils.destination import load_stage, snowflake_destination
from orchestrator.resources.snowflake import SnowflakeSettings


def test_discover_finds_knmi() -> None:
    assert discover()["knmi"] == "dlt_pipelines.pipelines.ingest.knmi.pipelines"


def test_load_stage_is_the_source_layer_stage_with_a_path_per_source() -> None:
    dev = SnowflakeSettings(database="DB_EXAMPLE_DEV", schema="DBT_USERNAME", environment="dev")
    prd = SnowflakeSettings(database="DB_EXAMPLE_PRD", environment="prd")
    assert load_stage(dev, "knmi") == "DB_EXAMPLE_DEV._SRC.ST_DLT/dbt_username/dlt/ingest/knmi"
    assert load_stage(prd, "knmi") == "DB_EXAMPLE_PRD._SRC.ST_DLT/dlt/ingest/knmi"


def test_load_window_never_starts_before_the_start_date() -> None:
    start, end = load_window(datetime(2026, 1, 10, tzinfo=UTC), days_back=30)
    assert (start, end) == (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 10, tzinfo=UTC))
    start, _ = load_window(datetime(2026, 9, 24, tzinfo=UTC), days_back=30)
    assert start == datetime(2026, 8, 25, tzinfo=UTC)


def test_merge_staging_tables_go_to_the_temporary_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "DB_EXAMPLE_DEV")
    monkeypatch.setenv("SNOWFLAKE_SCHEMA", "DBT_USERNAME")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    assert snowflake_destination("knmi").config_params["staging_dataset_name_layout"] == "dbt_username_tmp"
    monkeypatch.setenv("ENVIRONMENT", "prd")
    assert snowflake_destination("knmi").config_params["staging_dataset_name_layout"] == "_tmp"
