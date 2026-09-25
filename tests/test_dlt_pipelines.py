from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import dlt
import pytest
from dlt.common.configuration import known_sections, resolve_configuration
from dlt.common.schema import Schema
from dlt.destinations.impl.snowflake.configuration import SnowflakeClientConfiguration
from dlt.load.configuration import LoaderConfiguration

from dlt_pipelines.__main__ import discover
from dlt_pipelines.pipelines.ingest.knmi.source import load_window
from dlt_pipelines.utils.destination import load_stage, pipeline_name, snowflake_destination
from dlt_pipelines.utils.snowflake_stage import NamedFolderClient, NamedFolderLoadJob
from orchestrator.resources.snowflake import SnowflakeSettings


def test_discover_finds_knmi() -> None:
    assert discover()["knmi"] == "dlt_pipelines.pipelines.ingest.knmi.pipelines"


def test_load_stage_is_the_stage_of_the_source_schema_with_a_path_per_source() -> None:
    dev = SnowflakeSettings(database="DB_EXAMPLE_DEV", schema="DBT_USERNAME", environment="dev")
    prd = SnowflakeSettings(database="DB_EXAMPLE_PRD", environment="prd")
    assert load_stage(dev, "knmi") == "DB_EXAMPLE_DEV.DBT_USERNAME_SRC.ST_DEFAULT/dlt/ingest/knmi"
    assert load_stage(prd, "knmi") == "DB_EXAMPLE_PRD._SRC.ST_DEFAULT/dlt/ingest/knmi"


class FakeSqlClient:
    """Records the statements a load job runs instead of sending them to Snowflake."""

    capabilities = dlt.destinations.snowflake().capabilities()

    def __init__(self) -> None:
        self.executed: list[str] = []

    def make_qualified_table_name(self, name: str) -> str:
        return f'"DB_EXAMPLE_DEV"."DBT_USERNAME_SRC"."{name.upper()}"'

    @contextmanager
    def begin_transaction(self) -> Iterator[None]:
        yield

    def execute_sql(self, sql: str) -> None:
        self.executed.append(" ".join(sql.split()))


def test_each_load_goes_to_an_unquoted_pipeline_and_load_id_folder(tmp_path: Path) -> None:
    job = NamedFolderLoadJob(
        str(tmp_path / "knmi__climate_hourly.a1b2c3d4.0.jsonl"),
        SnowflakeClientConfiguration(),
        stage_name="DB_EXAMPLE_DEV.DBT_USERNAME_SRC.ST_DEFAULT/dlt/ingest/knmi",
        keep_staged_files=False,
        pipeline_name="ingest_knmi",
    )
    job.set_run_vars("1790329283.5731854", Schema("knmi__climate_hourly"), {"name": "knmi__climate_hourly"})
    sql_client = FakeSqlClient()
    job._job_client = cast(Any, SimpleNamespace(sql_client=sql_client))
    job.run()
    folder = "@DB_EXAMPLE_DEV.DBT_USERNAME_SRC.ST_DEFAULT/dlt/ingest/knmi/ingest_knmi__1790329283.5731854"
    put, copy, remove = sql_client.executed
    assert put.startswith("PUT 'file://") and put.endswith(f"'{folder}' OVERWRITE = TRUE, AUTO_COMPRESS = FALSE")
    assert copy.startswith('COPY INTO "DB_EXAMPLE_DEV"."DBT_USERNAME_SRC"."KNMI__CLIMATE_HOURLY"')
    assert f"FROM '{folder}/knmi__climate_hourly.a1b2c3d4.0.jsonl'" in copy
    assert remove == f"REMOVE '{folder}/knmi__climate_hourly.a1b2c3d4.0.jsonl'"


def test_destination_keeps_the_identity_of_dlts_snowflake_destination() -> None:
    destination = snowflake_destination("knmi")
    assert destination.destination_type == dlt.destinations.snowflake().destination_type
    assert destination.destination_name == "snowflake"
    assert destination.client_class is NamedFolderClient
    assert pipeline_name("knmi") == "ingest_knmi"


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


def test_merge_staging_tables_are_emptied_after_each_load() -> None:
    # Resolved like dlt's loader does, from the [load] section of .dlt/config.toml.
    config = resolve_configuration(LoaderConfiguration(), sections=(known_sections.LOAD,), accept_partial=True)
    assert config.truncate_staging_dataset is True
