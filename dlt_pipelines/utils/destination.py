"""The Snowflake destination and dataset every ingest pipeline loads into."""

from dlt.common.destination import Destination

from dlt_pipelines.utils.snowflake_stage import snowflake_named_folders
from orchestrator.resources.snowflake import SnowflakeSettings

SOURCE_LAYER = "src"
STAGING_LAYER = "tmp"
STAGE = "ST_DEFAULT"


def pipeline_name(source: str) -> str:
    """`ingest_<source>`: the dlt pipeline of a source (its state under `.dlt/data/pipelines/`, its stage folders)."""
    return f"ingest_{source}"


def snowflake_destination(source: str) -> Destination:
    """Build the destination of one source from the SNOWFLAKE_* environment variables (key-pair auth).

    dlt's Snowflake destination, except that each load goes into the stage folder
    `<pipeline>__<load id>` instead of `"<load id>"` (dlt_pipelines/utils/snowflake_stage.py).
    Credentials are only validated when a pipeline runs, so importing the pipelines (as Dagster
    does on every code-location load) works without a .env.
    """
    settings = SnowflakeSettings.from_env()
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

    Terraform creates `ST_DEFAULT` in every source-layer schema (terraform/stages.tf): the shared
    `DB_<PROJECT>_<ENV>._SRC.ST_DEFAULT`, and in dev each developer's own
    `DB_<PROJECT>_DEV.<SNOWFLAKE_SCHEMA>_SRC.ST_DEFAULT`, so the load files sit next to the tables they
    load. The path below it mirrors the Dagster asset key (`dlt/ingest/<source>/<entity>`); each load
    gets a folder `<pipeline>__<load id>` and dlt names each file after its table, so
    `LIST @_SRC.ST_DEFAULT/dlt/ingest/knmi/` shows every KNMI load.
    """
    return f"{settings.database}.{settings.schema_for_layer(SOURCE_LAYER)}.{STAGE}/dlt/ingest/{source}"


def source_dataset() -> str:
    """The source-layer schema: `_SRC`, or `<SNOWFLAKE_SCHEMA>_SRC` in dev (provisioned by Terraform).

    Lowercase because dlt normalizes dataset names that way and warns otherwise; Snowflake resolves
    the unquoted identifier to the same `_SRC` / `<PREFIX>_SRC` schema dbt reads from.
    """
    return SnowflakeSettings.from_env().schema_for_layer(SOURCE_LAYER).lower()
