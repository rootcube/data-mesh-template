"""The Snowflake destination and dataset every ingest pipeline loads into."""

import dlt
from dlt.common.destination import Destination

from orchestrator.resources.snowflake import SnowflakeSettings

SOURCE_LAYER = "src"
STAGE = "ST_DLT"


def snowflake_destination() -> Destination:
    """Build the destination from the SNOWFLAKE_* environment variables (key-pair auth).

    Credentials are only validated when a pipeline runs, so importing the pipelines (as Dagster
    does on every code-location load) works without a .env.
    """
    settings = SnowflakeSettings.from_env()
    return dlt.destinations.snowflake(credentials=settings.dlt_credentials(), stage_name=load_stage(settings))


def load_stage(settings: SnowflakeSettings) -> str:
    """The internal stage dlt PUTs its files into before COPY INTO: `DB_<PROJECT>_<ENV>._SRC.ST_DLT`.

    Terraform creates it in the provisioned source layer of every project database (terraform/stages.tf),
    so it is the same stage in every environment; only the tables move to the personal schema in dev.
    """
    return f"{settings.database}._{SOURCE_LAYER.upper()}.{STAGE}"


def source_dataset() -> str:
    """The source-layer schema: `_SRC`, or `<SNOWFLAKE_SCHEMA>_SRC` in dev (created on first load).

    Lowercase because dlt normalizes dataset names that way and warns otherwise; Snowflake resolves
    the unquoted identifier to the same `_SRC` / `<PREFIX>_SRC` schema dbt reads from.
    """
    return SnowflakeSettings.from_env().schema_for_layer(SOURCE_LAYER).lower()
