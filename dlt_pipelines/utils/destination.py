"""The destination and dataset every ingest pipeline loads into: Snowflake, or the local DuckDB file."""

import logging

import dlt
from dlt.common.destination import Destination

from dlt_pipelines.utils.snowflake_stage import snowflake_named_folders
from orchestrator.resources.snowflake import SnowflakeSettings

LOGGER = logging.getLogger(__name__)

SOURCE_LAYER = "src"
STAGING_LAYER = "tmp"
STAGE = "ST_DEFAULT"


def pipeline_name(source: str) -> str:
    """`ingest_<source>`: the dlt pipeline of a source (its state under `.dlt/data/pipelines/`, its stage folders)."""
    return f"ingest_{source}"


def destination(source: str) -> Destination:
    """The destination of one source: the DuckDB file of the `local` environment, Snowflake everywhere else."""
    settings = SnowflakeSettings.from_env()
    if settings.is_local:
        return duckdb_destination(settings)
    return snowflake_destination(source)


def duckdb_destination(settings: SnowflakeSettings) -> Destination:
    """dlt's DuckDB destination on the file of the `local` environment (DUCKDB_PATH, set by the justfile and .envrc).

    Without the path dlt would quietly write `<pipeline>.duckdb` into the working directory, so this
    fails at import instead; the Snowflake branch below only warns, because a run without
    credentials fails on its own.
    """
    if not settings.duckdb_path:
        raise ValueError(
            "ENVIRONMENT=local needs DUCKDB_PATH (the justfile and .envrc set it): run through `just` or direnv."
        )
    # dlt's default staging schema (`<dataset>_staging`) rather than the `_TMP` layer the Snowflake
    # branch uses: nothing needs provisioning in a DuckDB file, and dbt creates `<PREFIX>_TMP` in
    # uppercase for its test failures, which dlt's lowercase lookup then misses and fails to create.
    return dlt.destinations.duckdb(credentials=settings.duckdb_path)


def snowflake_destination(source: str) -> Destination:
    """Build the destination of one source from the SNOWFLAKE_* environment variables (key-pair auth).

    dlt's Snowflake destination, except that each load goes into the stage folder
    `<pipeline>__<load id>` instead of `"<load id>"` (dlt_pipelines/utils/snowflake_stage.py).
    Credentials are only validated when a pipeline runs, so importing the pipelines (as Dagster
    does on every code-location load) works without a .env.
    """
    settings = SnowflakeSettings.from_env()
    if missing := settings.missing():
        # A warning, not an exception: this runs at import, and importing has to work without a
        # .env (the Dagster code location loads the pipelines on every start, CI validates it with
        # no .env at all). The run itself fails, but on dlt's own field names
        # (DESTINATION__SNOWFLAKE__CREDENTIALS__DATABASE), so name the platform's variables here.
        # An unset SNOWFLAKE_DATABASE also leaves the stage path below starting with a dot.
        LOGGER.warning("dlt destination for %s is incomplete, unset: %s", source, ", ".join(missing))
    return snowflake_named_folders(
        pipeline_name=pipeline_name(source),
        credentials=settings.dlt_credentials(),
        stage_name=load_stage(settings, source),
        # `merge` loads into a staging table first; keep those in the temporary layer (`_TMP`, or the
        # personal `<PREFIX>_TMP` in dev) instead of dlt's default `<dataset>_staging` schema, which
        # nobody provisions and the ingest role may not create. `truncate_staging_dataset` in
        # .dlt/config.toml empties them after each load, so raw rows do not linger in the shared `_TMP`.
        staging_dataset_name_layout=settings.schema_for_layer(STAGING_LAYER).lower(),
    )


def load_stage(settings: SnowflakeSettings, source: str) -> str:
    """The stage path dlt PUTs a source's load files into: `<source schema>.ST_DEFAULT/dlt/ingest/<source>`.

    Terraform creates `ST_DEFAULT` in every source-layer schema
    (terraform/components/snowflake-project/stages.tf): the shared
    `DB_<PROJECT>_<ENV>._SRC.ST_DEFAULT`, and in dev each developer's own
    `DB_<PROJECT>_DEV.<SNOWFLAKE_SCHEMA>_SRC.ST_DEFAULT`, so the load files sit next to the tables they
    load. The path below it mirrors the Dagster asset key (`dlt/ingest/<source>/<entity>`); each load
    gets a folder `<pipeline>__<load id>` and dlt names each file after its table, so
    `LIST @_SRC.ST_DEFAULT/dlt/ingest/knmi/` shows every KNMI load.
    """
    return f"{settings.database}.{settings.schema_for_layer(SOURCE_LAYER)}.{STAGE}/dlt/ingest/{source}"


def source_dataset() -> str:
    """The source-layer schema: `_SRC`, or `<SNOWFLAKE_SCHEMA>_SRC` in dev (provisioned by Terraform) and local.

    Lowercase because dlt normalizes dataset names that way and warns otherwise; Snowflake resolves
    the unquoted identifier to the same `_SRC` / `<PREFIX>_SRC` schema dbt reads from.
    """
    return SnowflakeSettings.from_env().schema_for_layer(SOURCE_LAYER).lower()
