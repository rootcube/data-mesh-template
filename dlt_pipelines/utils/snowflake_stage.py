"""dlt's Snowflake destination with one readable folder per load in the stage.

dlt PUTs every file of a load into `<stage_name>/"<load id>"/`: a folder named after the bare load
id, double quotes included (`SnowflakeLoadJob.run` in dlt 1.30). The destination below names that
folder `<pipeline>__<load id>`, without quotes, so a stage listing shows which pipeline wrote what:

    <source schema>.ST_DEFAULT/dlt/ingest/knmi/ingest_knmi__1790329283.5731854/knmi__climate_hourly.a1b2c3d4.0.jsonl

The file names stay dlt's own (`<table>.<file id>.<retry>.<format>`): PUT keeps the local name.
Everything else is dlt's Snowflake destination unchanged, and it reports dlt's destination type, so
pipeline state and `[destination.snowflake]` config sections are the same as with
`dlt.destinations.snowflake`.

`NamedFolderLoadJob.run` is a copy of dlt's `SnowflakeLoadJob.run` with only the folder changed;
compare it with dlt's when upgrading (tests/test_dlt_pipelines.py pins the statements it runs).
"""

from typing import Any, cast

from dlt.common.data_writers.escape import escape_snowflake_literal
from dlt.common.destination.client import LoadJob, PreparedTableSchema
from dlt.common.destination.reference import DestinationReference
from dlt.common.storages.file_storage import FileStorage
from dlt.common.typing import TLoaderFileFormat
from dlt.destinations import snowflake
from dlt.destinations.impl.snowflake.snowflake import SnowflakeClient, SnowflakeLoadJob
from dlt.destinations.impl.snowflake.utils import gen_copy_sql
from dlt.destinations.job_impl import ReferenceFollowupJobRequest
from dlt.destinations.path_utils import get_file_format_and_compression


class NamedFolderLoadJob(SnowflakeLoadJob):
    """PUT + COPY INTO like dlt's job, into the folder `<pipeline>__<load id>` of the stage."""

    def __init__(self, *args: Any, pipeline_name: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pipeline_name = pipeline_name

    @property
    def load_folder(self) -> str:
        return f"{self._pipeline_name}__{self._load_id}"

    def run(self) -> None:
        self._sql_client = self._job_client.sql_client

        # resolve reference
        is_local_file = not ReferenceFollowupJobRequest.is_reference_job(self._file_path)
        file_url = self._file_path if is_local_file else ReferenceFollowupJobRequest.resolve_reference(self._file_path)
        # take file name
        file_name = FileStorage.get_file_name_from_file_path(file_url)
        file_format, _ = get_file_format_and_compression(file_name)

        qualified_table_name = self._sql_client.make_qualified_table_name(self.load_table_name)
        # this means we have a local file
        stage_folder: str = ""
        stage_file_path: str = ""
        if is_local_file:
            if not self._stage_name:
                # Use implicit table stage by default: "SCHEMA_NAME"."%TABLE_NAME"
                self._stage_name = self._sql_client.make_qualified_table_name("%" + self.load_table_name)
            # The one change from dlt: `<pipeline>__<load id>` instead of `"<load id>"`.
            stage_folder = f"@{self._stage_name}/{self.load_folder}"
            stage_file_path = f"{stage_folder}/{file_name}"

        stage_bucket_url = None
        if self._config.staging_config and self._config.staging_config.bucket_url:
            stage_bucket_url = self._config.staging_config.bucket_url

        # null fields in structured columns only load with the vectorized scanner
        use_vectorized_scanner = self._config.use_vectorized_scanner or (
            self._config.use_nested_types and file_format == "parquet"
        )

        copy_sql = gen_copy_sql(
            file_url=file_url,
            qualified_table_name=qualified_table_name,
            loader_file_format=cast(TLoaderFileFormat, file_format),
            is_case_sensitive=self._sql_client.capabilities.generates_case_sensitive_identifiers(),
            stage_name=self._stage_name,
            stage_bucket_url=stage_bucket_url,
            local_stage_file_path=stage_file_path,
            staging_credentials=self._staging_credentials,
            csv_format=self._config.csv_format,
            use_vectorized_scanner=use_vectorized_scanner,
        )

        with self._sql_client.begin_transaction():
            # PUT and COPY in one tx if local file, otherwise only copy
            if is_local_file:
                # backslash is an escape character in snowflake string literals, forward
                # slashes are valid in PUT file URIs also on Windows
                file_uri = "file://" + self._file_path.replace("\\", "/")
                self._sql_client.execute_sql(
                    f"PUT {escape_snowflake_literal(file_uri)}"
                    f" {escape_snowflake_literal(stage_folder)} OVERWRITE = TRUE, AUTO_COMPRESS ="
                    " FALSE"
                )
            self._sql_client.execute_sql(copy_sql)
            if stage_file_path and not self._keep_staged_files:
                self._sql_client.execute_sql(f"REMOVE {escape_snowflake_literal(stage_file_path)}")


class NamedFolderClient(SnowflakeClient):
    """dlt's Snowflake job client; loads local files with NamedFolderLoadJob once `pipeline_name` is set."""

    pipeline_name: str | None = None

    def create_load_job(
        self, table: PreparedTableSchema, file_path: str, load_id: str, restore: bool = False
    ) -> LoadJob:
        job = super().create_load_job(table, file_path, load_id, restore)
        if type(job) is SnowflakeLoadJob and self.pipeline_name:
            job = NamedFolderLoadJob(
                file_path,
                self.config,
                stage_name=self.config.stage_name,
                keep_staged_files=self.config.keep_staged_files,
                staging_credentials=self.config.staging_config.credentials if self.config.staging_config else None,
                pipeline_name=self.pipeline_name,
            )
        return job


class snowflake_named_folders(snowflake):  # noqa: N801 - dlt names destination factories in lower case
    """`dlt.destinations.snowflake` that puts each load in the stage folder `<pipeline>__<load id>`."""

    # dlt reads the factory's keyword defaults from this class's __init__ signature
    __orig_base__ = snowflake

    def __init__(self, *, pipeline_name: str, **kwargs: Any) -> None:
        self._pipeline_name = pipeline_name
        super().__init__(**kwargs)

    @property
    def destination_type(self) -> str:
        return DestinationReference.normalize_type(f"{snowflake.__module__}.{snowflake.__qualname__}")

    @property
    def client_class(self) -> type[SnowflakeClient]:
        return NamedFolderClient

    def client(self, *args: Any, **kwargs: Any) -> NamedFolderClient:
        client = cast(NamedFolderClient, super().client(*args, **kwargs))
        client.pipeline_name = self._pipeline_name
        return client
