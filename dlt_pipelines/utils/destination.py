"""The Snowflake destination and dataset every ingest pipeline loads into."""

import dlt
from dlt.common.destination import Destination

from orchestrator.resources.snowflake import SnowflakeSettings

SOURCE_LAYER = "src"


def snowflake_destination() -> Destination:
    """Build the destination from the SNOWFLAKE_* environment variables (key-pair auth).

    Credentials are only validated when a pipeline runs, so importing the pipelines (as Dagster
    does on every code-location load) works without a .env.
    """
    return dlt.destinations.snowflake(credentials=SnowflakeSettings.from_env().dlt_credentials())


def source_dataset() -> str:
    """The source-layer schema: `_SRC`, or `<SNOWFLAKE_SCHEMA>_SRC` in dev (created on first load).

    Lowercase because dlt normalizes dataset names that way and warns otherwise; Snowflake resolves
    the unquoted identifier to the same `_SRC` / `<PREFIX>_SRC` schema dbt reads from.
    """
    return SnowflakeSettings.from_env().schema_for_layer(SOURCE_LAYER).lower()
