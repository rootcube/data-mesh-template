"""Dagster code location `dlt`: every dlt load under dlt_pipelines/pipelines/ingest.

Each source folder carries a defs.yaml (dagster_dlt.DltLoadCollectionComponent) that turns the
module-level dlt `source` and `pipeline` objects into Dagster assets. This module only loads
that component tree and adds one job for every load, with its daily schedule.
"""

from pathlib import Path

from dagster import (
    AssetSelection,
    ComponentTree,
    DefaultScheduleStatus,
    Definitions,
    ScheduleDefinition,
    define_asset_job,
)

import dlt_pipelines as _dlt_pipelines
from orchestrator.resources.snowflake import SnowflakeSettings

# src/orchestrator/locations/dlt/definitions.py -> repository root
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _build_defs() -> Definitions:
    loaded = ComponentTree.from_module(defs_module=_dlt_pipelines, project_root=_PROJECT_ROOT).build_defs()
    job_all = define_asset_job(
        name="job__dlt__ingest_all",
        selection=AssetSelection.key_prefixes(["dlt", "ingest"]),
        description="Run every dlt ingest pipeline.",
    )
    # Daily at 06:00 UTC, when yesterday's KNMI hours are complete. Stopped in dev and dummy, so
    # nothing loads by itself on a laptop; running everywhere else.
    schedule_all = ScheduleDefinition(
        name="schedule__dlt__ingest_all",
        job=job_all,
        cron_schedule="0 6 * * *",
        default_status=DefaultScheduleStatus.STOPPED
        if SnowflakeSettings.from_env().is_personal
        else DefaultScheduleStatus.RUNNING,
    )
    return Definitions.merge(loaded, Definitions(jobs=[job_all], schedules=[schedule_all]))


defs = _build_defs()
