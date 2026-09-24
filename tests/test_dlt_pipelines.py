from datetime import UTC, datetime

from dlt_pipelines.__main__ import discover
from dlt_pipelines.pipelines.ingest.knmi.source import load_window
from dlt_pipelines.utils.destination import load_stage
from orchestrator.resources.snowflake import SnowflakeSettings


def test_discover_finds_knmi() -> None:
    assert discover()["knmi"] == "dlt_pipelines.pipelines.ingest.knmi.pipelines"


def test_load_stage_is_the_provisioned_source_layer_stage_in_every_environment() -> None:
    dev = SnowflakeSettings(database="DB_EXAMPLE_DEV", schema="DBT_USERNAME", environment="dev")
    prd = SnowflakeSettings(database="DB_EXAMPLE_PRD", environment="prd")
    assert load_stage(dev) == "DB_EXAMPLE_DEV._SRC.ST_DLT"
    assert load_stage(prd) == "DB_EXAMPLE_PRD._SRC.ST_DLT"


def test_load_window_never_starts_before_the_start_date() -> None:
    start, end = load_window(datetime(2026, 1, 10, tzinfo=UTC), days_back=30)
    assert (start, end) == (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 10, tzinfo=UTC))
    start, _ = load_window(datetime(2026, 9, 24, tzinfo=UTC), days_back=30)
    assert start == datetime(2026, 8, 25, tzinfo=UTC)
