"""Dagster code location `dlt`: every dlt load under dlt_pipelines/pipelines/ingest.

Each source folder carries a defs.yaml (dagster_dlt.DltLoadCollectionComponent) that turns the
module-level dlt `source` and `pipeline` objects into Dagster assets. This module only loads
that component tree and derives the jobs and schedules: per source folder (found the way
`just dlt list` finds them) `job__dlt__ingest_<source>` with a daily `schedule__dlt__ingest_<source>`,
and for every load `job__dlt__ingest_all` with `schedule__dlt__ingest_all`. The per-source
schedules carry the daily load; the all-sources schedule starts stopped everywhere, an opt-in for
loading everything in one run instead (start it and stop the per-source ones, or a load runs twice).
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
from dlt_pipelines.__main__ import discover
from orchestrator.resources.snowflake import SnowflakeSettings

# src/orchestrator/locations/dlt/definitions.py -> repository root
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
# Daily at 06:00 UTC, when yesterday's KNMI hours are complete.
INGEST_CRON = "0 6 * * *"


def _build_defs() -> Definitions:
    loaded = ComponentTree.from_module(defs_module=_dlt_pipelines, project_root=_PROJECT_ROOT).build_defs()
    # Stopped in dev and dummy, so nothing loads by itself on a laptop; running everywhere else.
    per_source_status = (
        DefaultScheduleStatus.STOPPED if SnowflakeSettings.from_env().is_personal else DefaultScheduleStatus.RUNNING
    )
    jobs = [
        define_asset_job(
            name=f"job__dlt__ingest_{source}",
            selection=AssetSelection.key_prefixes(["dlt", "ingest", source]),
            description=f"Run the dlt ingest pipeline of {source}.",
        )
        for source in sorted(discover())
    ]
    schedules = [
        ScheduleDefinition(
            name=job.name.replace("job__", "schedule__", 1),
            job=job,
            cron_schedule=INGEST_CRON,
            default_status=per_source_status,
        )
        for job in jobs
    ]
    job_all = define_asset_job(
        name="job__dlt__ingest_all",
        selection=AssetSelection.key_prefixes(["dlt", "ingest"]),
        description="Run every dlt ingest pipeline.",
    )
    schedule_all = ScheduleDefinition(
        name="schedule__dlt__ingest_all",
        job=job_all,
        cron_schedule=INGEST_CRON,
        default_status=DefaultScheduleStatus.STOPPED,
        description="Opt-in: every load in one run. Start it and stop the per-source schedules, or a load runs twice.",
    )
    return Definitions.merge(loaded, Definitions(jobs=[*jobs, job_all], schedules=[*schedules, schedule_all]))


defs = _build_defs()
