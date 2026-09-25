"""The Snowflake destination and dataset every ingest pipeline loads into."""

import dlt
from dlt.common.destination import Destination

from orchestrator.resources.snowflake import SnowflakeSettings

SOURCE_LAYER = "src"
STAGING_LAYER = "tmp"
STAGE = "ST_DLT"


def snowflake_destination(source: str) -> Destination:
    """Build the destination of one source from the SNOWFLAKE_* environment variables (key-pair auth).

    Credentials are only validated when a pipeline runs, so importing the pipelines (as Dagster
    does on every code-location load) works without a .env.
    """
    settings = SnowflakeSettings.from_env()
    return dlt.destinations.snowflake(
        credentials=settings.dlt_credentials(),
        stage_name=load_stage(settings, source),
        # `merge` loads into a staging table first; keep those in the temporary layer (`_TMP`, or the
        # personal `<PREFIX>_TMP` in dev) instead of dlt's default `<dataset>_staging` schema, which
        # nobody provisions and the ingest role may not create.
        staging_dataset_name_layout=settings.schema_for_layer(STAGING_LAYER).lower(),
    )


def load_stage(settings: SnowflakeSettings, source: str) -> str:
    """The stage path dlt PUTs a source's load files into: `DB_<PROJECT>_<ENV>._SRC.ST_DLT/dlt/ingest/<source>`.

    Terraform creates the stage in the provisioned source layer of every project database
    (terraform/stages.tf), so it is the same stage in every environment. The path below it mirrors
    the Dagster asset key (`dlt/ingest/<source>/<entity>`); dlt adds a folder per load id and names
    each file after its table, so `LIST @_SRC.ST_DLT/dlt/ingest/knmi/` shows every KNMI load. In dev
    the path starts with your lowercased SNOWFLAKE_SCHEMA prefix, the way the tables live in
    `<SNOWFLAKE_SCHEMA>_SRC`.
    """
    path = f"dlt/ingest/{source}"
    if settings.is_personal and settings.schema:
        path = f"{settings.schema.lower()}/{path}"
    return f"{settings.database}._{SOURCE_LAYER.upper()}.{STAGE}/{path}"


def source_dataset() -> str:
    """The source-layer schema: `_SRC`, or `<SNOWFLAKE_SCHEMA>_SRC` in dev (created on first load).

    Lowercase because dlt normalizes dataset names that way and warns otherwise; Snowflake resolves
    the unquoted identifier to the same `_SRC` / `<PREFIX>_SRC` schema dbt reads from.
    """
    return SnowflakeSettings.from_env().schema_for_layer(SOURCE_LAYER).lower()
