"""The shared dlt layer: the destination, the stage path and the load job per stage folder.

Tests of the example KNMI source itself live in tests/test_dlt_knmi.py.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import dlt
import pytest
from dlt.common.configuration import known_sections, resolve_configuration
from dlt.common.schema import Schema
from dlt.destinations.impl.snowflake.configuration import SnowflakeClientConfiguration
from dlt.load.configuration import LoaderConfiguration

from dlt_pipelines.utils.destination import load_stage, pipeline_name, snowflake_destination
from dlt_pipelines.utils.snowflake_stage import NamedFolderClient, NamedFolderLoadJob, snowflake_named_folders
from orchestrator.resources.snowflake import APPLICATION, SnowflakeSettings

STAGE = "DB_EXAMPLE_DEV.DBT_USERNAME_SRC.ST_DEFAULT/dlt/ingest/knmi"
LOAD_ID = "1790329283.5731854"


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
        stage_name=STAGE,
        keep_staged_files=False,
        pipeline_name="ingest_knmi",
    )
    job.set_run_vars(LOAD_ID, Schema("knmi"), {"name": "knmi__climate_hourly"})
    sql_client = FakeSqlClient()
    job._job_client = cast(Any, SimpleNamespace(sql_client=sql_client))
    job.run()
    folder = f"@{STAGE}/ingest_knmi__{LOAD_ID}"
    put, copy, remove = sql_client.executed
    assert put.startswith("PUT 'file://") and put.endswith(f"'{folder}' OVERWRITE = TRUE, AUTO_COMPRESS = FALSE")
    assert copy.startswith('COPY INTO "DB_EXAMPLE_DEV"."DBT_USERNAME_SRC"."KNMI__CLIMATE_HOURLY"')
    assert f"FROM '{folder}/knmi__climate_hourly.a1b2c3d4.0.jsonl'" in copy
    assert remove == f"REMOVE '{folder}/knmi__climate_hourly.a1b2c3d4.0.jsonl'"


def test_the_client_hands_data_files_to_a_named_folder_job_and_passes_other_jobs_through(tmp_path: Path) -> None:
    # The whole path dlt takes when a load starts: factory -> client -> job, with credentials that
    # are never connected with. A dlt upgrade that stops this from returning a NamedFolderLoadJob
    # puts every load back in dlt's quoted "<load id>" folder without failing.
    destination = snowflake_named_folders(
        pipeline_name="ingest_knmi",
        credentials="snowflake://user:pass@ORG-ACCOUNT/DB_EXAMPLE_DEV?warehouse=WH_EXAMPLE_DEV&role=RL",
        stage_name=STAGE,
    )
    # `_bind_dataset_name` is how dlt's own pipeline hands the dataset to a destination config.
    config = SnowflakeClientConfiguration()._bind_dataset_name(dataset_name="dbt_username_src")
    client = destination.client(Schema("knmi"), config)
    table = cast(Any, {"name": "knmi__climate_hourly"})

    job = client.create_load_job(table, str(tmp_path / "knmi__climate_hourly.a1b2c3d4.0.jsonl"), LOAD_ID)
    assert isinstance(job, NamedFolderLoadJob)
    job.set_run_vars(LOAD_ID, Schema("knmi"), table)
    assert job.load_folder == f"ingest_knmi__{LOAD_ID}"

    # dlt's own jobs for .sql files are not load jobs of the destination; they stay untouched.
    sql_file = tmp_path / "knmi__climate_hourly.a1b2c3d4.0.sql"
    sql_file.write_text("SELECT 1")
    assert not isinstance(client.create_load_job(table, str(sql_file), LOAD_ID), NamedFolderLoadJob)


def test_destination_keeps_the_identity_of_dlts_snowflake_destination() -> None:
    destination = snowflake_destination("knmi")
    assert destination.destination_type == dlt.destinations.snowflake().destination_type
    assert destination.destination_name == "snowflake"
    assert destination.client_class is NamedFolderClient
    assert pipeline_name("knmi") == "ingest_knmi"


def test_dlt_sessions_carry_the_platforms_application_id() -> None:
    assert snowflake_destination("knmi").config_params["credentials"]["application"] == APPLICATION


def test_merge_staging_tables_go_to_the_temporary_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "DB_EXAMPLE_DEV")
    monkeypatch.setenv("SNOWFLAKE_SCHEMA", "DBT_USERNAME")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    assert snowflake_destination("knmi").config_params["staging_dataset_name_layout"] == "dbt_username_tmp"
    monkeypatch.setenv("ENVIRONMENT", "prd")
    assert snowflake_destination("knmi").config_params["staging_dataset_name_layout"] == "_tmp"


def test_merge_staging_tables_are_emptied_after_each_load() -> None:
    # Resolved like dlt's loader does, from the [load] section of .dlt/config.toml (conftest.py
    # points DLT_PROJECT_DIR at the repo so this holds from any working directory).
    config = resolve_configuration(LoaderConfiguration(), sections=(known_sections.LOAD,), accept_partial=True)
    assert config.truncate_staging_dataset is True
