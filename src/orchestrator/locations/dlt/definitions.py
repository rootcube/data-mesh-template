"""Dagster code location `dlt`: every dlt load under dlt_pipelines/pipelines/ingest.

Each source folder carries a defs.yaml (dagster_dlt.DltLoadCollectionComponent) that turns the
module-level dlt `source` and `pipeline` objects into Dagster assets. This module only loads
that component tree and adds one convenience job for the Launchpad, plus the daily schedule that
drives it.
"""

from pathlib import Path

from dagster import (
    AssetSelection,
    Backoff,
    ComponentTree,
    DefaultScheduleStatus,
    Definitions,
    RetryPolicy,
    ScheduleDefinition,
    define_asset_job,
)

import dlt_pipelines as _dlt_pipelines

# src/orchestrator/locations/dlt/definitions.py -> repository root
_PROJECT_ROOT = Path(__file__).resolve().parents[4]

# When the daily ingest runs (UTC; add execution_timezone below for a local wall clock). Change it
# here: one cron covers every source, and a source that needs its own cadence gets its own
# ScheduleDefinition on a narrower AssetSelection.
_INGEST_CRON = "0 5 * * *"


def _build_defs() -> Definitions:
    loaded = ComponentTree.from_module(defs_module=_dlt_pipelines, project_root=_PROJECT_ROOT).build_defs()
    job_all = define_asset_job(
        name="job_dlt_ingest_all",
        selection=AssetSelection.key_prefixes(["dlt", "ingest"]),
        description="Run every dlt ingest pipeline.",
        # A source API that rate-limits or times out is the usual failure. Every pipeline merges on
        # a primary key, so re-running an overlapping window is safe.
        op_retry_policy=RetryPolicy(max_retries=2, delay=30, backoff=Backoff.EXPONENTIAL),
    )
    schedule_daily = ScheduleDefinition(
        name="schedule_dlt_ingest_daily",
        job=job_all,
        cron_schedule=_INGEST_CRON,
        # Shipped stopped on purpose: `just start` must never fire an ingest run unasked. Turn it on
        # under Automation in the UI (it stays on, in .dagster/), or ship RUNNING once deployed.
        default_status=DefaultScheduleStatus.STOPPED,
        description="Daily run of job_dlt_ingest_all.",
    )
    return Definitions.merge(loaded, Definitions(jobs=[job_all], schedules=[schedule_daily]))


defs = _build_defs()
