"""The source-freshness chain of one dbt location: check every hour, rebuild what got fresher.

`job__<location>__source_freshness` runs `dbt source freshness` (its schedule fires every hour)
and records what dbt found as one asset observation per source, `max_loaded_at` in its metadata.
`job__<location>__build_fresher` reads those observations back when it runs and builds the
downstream of exactly the sources whose `max_loaded_at` changed since its last successful run
started: `dbt build --select source:<source>.<table>+ ...`, dbt's `source_status:fresher+` with
the event log as the state. Launched by hand or by the sensor, it decides for itself, and it
streams dbt's results into Dagster: a materialization per model, a check result per test.
`sensor__<location>__source_freshness` applies the same rule every five minutes and launches the
job when any source got fresher and no run of it is in progress. A source takes part when its
YAML carries a `freshness` block and a `loaded_at_field` (or `loaded_at_query`); dbt skips the
others.

The hand-off between the jobs and the sensor is the Dagster event log, not dbt's `sources.json`:
each run may have its own pod (Kubernetes), the sensor runs in the code server, and the event log
is the instance storage they share (Postgres there, SQLite under `dagster dev`).
"""

import json
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from dagster import (
    AssetKey,
    AssetObservation,
    AssetRecordsFilter,
    DagsterInstance,
    DagsterRunStatus,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    Definitions,
    OpExecutionContext,
    RunRequest,
    RunsFilter,
    ScheduleDefinition,
    SensorEvaluationContext,
    SkipReason,
    job,
    op,
    sensor,
)
from dagster_dbt import DbtCliResource, DbtProjectComponent
from dagster_dbt.core.dbt_event_iterator import DbtDagsterEventType

FRESHNESS_CRON = "0 * * * *"  # dbt source freshness, every hour on the hour
SENSOR_INTERVAL_SECONDS = 300  # the sensor re-reads the observations every five minutes
FRESHNESS_METADATA = "max_loaded_at"  # the observation metadata the freshness job writes, the others read
IN_PROGRESS = [
    DagsterRunStatus.QUEUED,
    DagsterRunStatus.NOT_STARTED,
    DagsterRunStatus.STARTING,
    DagsterRunStatus.STARTED,
    DagsterRunStatus.CANCELING,
]


def diff_freshness(results: Iterable[Mapping[str, Any]], previous: Mapping[str, str]) -> dict[str, str]:
    """The sources of `results` whose `max_loaded_at` differs from `previous`, unique_id -> max_loaded_at.

    A source without `max_loaded_at` (dbt could not query it) never counts as fresher, so a
    transient error never looks like new data.
    """
    changed: dict[str, str] = {}
    for result in results:
        unique_id = result.get("unique_id") or ""
        max_loaded_at = result.get("max_loaded_at")
        if unique_id and max_loaded_at and max_loaded_at != previous.get(unique_id):
            changed[unique_id] = max_loaded_at
    return changed


def freshness_observations(
    results: Iterable[Mapping[str, Any]], source_asset_keys: Mapping[str, AssetKey]
) -> list[AssetObservation]:
    """One observation per source of a sources.json that dbt could query, on the source's asset key."""
    observations = []
    for result in results:
        asset_key = source_asset_keys.get(result.get("unique_id") or "")
        max_loaded_at = result.get("max_loaded_at")
        if asset_key and max_loaded_at:
            observations.append(AssetObservation(asset_key=asset_key, metadata={FRESHNESS_METADATA: max_loaded_at}))
    return observations


def observed_freshness(
    instance: DagsterInstance, source_asset_keys: Mapping[str, AssetKey], before: float | None = None
) -> list[dict[str, str]]:
    """The latest `max_loaded_at` observed per source, before the timestamp `before` when given.

    In the shape of sources.json results. A source whose latest observation carries no
    `max_loaded_at` (never checked, or observed by something else) is left out.
    """
    results = []
    for unique_id, asset_key in source_asset_keys.items():
        records_filter = AssetRecordsFilter(asset_key=asset_key, before_timestamp=before)
        records = instance.fetch_observations(records_filter, limit=1).records
        observation = records[0].asset_observation if records else None
        value = observation.metadata.get(FRESHNESS_METADATA) if observation else None
        if value is not None:
            results.append({"unique_id": unique_id, "max_loaded_at": str(value.value)})
    return results


def last_success_start(instance: DagsterInstance, job_name: str) -> float | None:
    """When the last successful run of `job_name` started; None before its first success."""
    records = instance.get_run_records(RunsFilter(job_name=job_name, statuses=[DagsterRunStatus.SUCCESS]), limit=1)
    return records[0].start_time if records else None


def fresher_sources(instance: DagsterInstance, source_asset_keys: Mapping[str, AssetKey], job_name: str) -> dict[str, str]:
    """The sources whose `max_loaded_at` changed since the last successful run of `job_name` started.

    The values observed before that start are what the run built from, so a source is fresher
    when its latest observation differs from them. Before the first success every observed
    source is fresher; a failed run moves nothing, so the next run builds the same sources again.
    """
    since = last_success_start(instance, job_name)
    built = observed_freshness(instance, source_asset_keys, before=since) if since is not None else []
    previous = {result["unique_id"]: result["max_loaded_at"] for result in built}
    return diff_freshness(observed_freshness(instance, source_asset_keys), previous)


def is_running(instance: DagsterInstance, job_name: str) -> bool:
    """Whether a run of `job_name` is queued or in progress."""
    return bool(instance.get_run_records(RunsFilter(job_name=job_name, statuses=IN_PROGRESS), limit=1))


def dbt_selector(unique_ids: Iterable[str]) -> str:
    """`source:<source>.<table>+ ...`: the given sources and everything downstream of them."""
    tokens: list[str] = []
    for unique_id in unique_ids:
        parts = unique_id.split(".", 3)  # source.<package>.<source name>.<table>
        if len(parts) != 4 or parts[0] != "source":
            raise ValueError(f"not a dbt source unique_id: {unique_id!r}")
        tokens.append(f"source:{parts[2]}.{parts[3]}+")
    return " ".join(tokens)


def build_source_freshness_defs(
    *,
    project_name: str,
    component: DbtProjectComponent,
    source_asset_keys: Mapping[str, AssetKey],
    run_by_default: bool,
) -> Definitions:
    """The two jobs, the schedule and the sensor of the chain, named after the location.

    `component` is the location's dbt component: its project to run, its translator to key the
    results of `build_fresher` like the dbt assets. `source_asset_keys` maps a source's unique_id
    to its Dagster asset key; the freshness job records its observations on those assets, and
    `build_fresher` and the sensor read them back. `run_by_default` decides whether the schedule
    and the sensor start running when the location loads (off in personal environments, where
    nothing should fire by itself).
    """
    project = component.dbt_project
    freshness_dir = Path(project.project_dir) / project.target_path / "freshness"
    sources_json = freshness_dir / "sources.json"
    build_fresher_name = f"job__{project_name}__build_fresher"

    @op(name=f"op__{project_name}__source_freshness")
    def check_source_freshness(context: OpExecutionContext, dbt: DbtCliResource) -> None:
        """`dbt source freshness`, recorded as observations. A stale source is a warning here, not a failed run."""
        dbt.cli(["source", "freshness"], context=context, target_path=freshness_dir, raise_on_error=False).wait()
        if not sources_json.exists():
            raise RuntimeError(f"dbt source freshness wrote no {sources_json}; see {freshness_dir / 'dbt.log'}")
        results = json.loads(sources_json.read_text()).get("results", [])
        for observation in freshness_observations(results, source_asset_keys):
            context.log_event(observation)

    @job(
        name=f"job__{project_name}__source_freshness",
        description=f"dbt source freshness for {project_name}, recorded as an observation per source.",
    )
    def source_freshness() -> None:
        check_source_freshness()

    @op(name=f"op__{project_name}__build_fresher", out={})
    def build_fresher(context: OpExecutionContext, dbt: DbtCliResource) -> Iterator[DbtDagsterEventType]:
        """`dbt build --select source:<s>+ ...` for the sources that got fresher, streamed as asset events."""
        changed = fresher_sources(context.instance, source_asset_keys, build_fresher_name)
        if not changed:
            context.log.info(f"no source got fresher since the last successful {build_fresher_name}: nothing to build")
            return
        context.log.info(f"{len(changed)} sources got fresher: {sorted(changed)}")
        yield from dbt.cli(
            ["build", "--select", dbt_selector(changed)],
            context=context,
            manifest=project.manifest_path,
            dagster_dbt_translator=component.translator,
        ).stream()

    @job(
        name=build_fresher_name,
        description=(
            f"dbt build downstream of the {project_name} sources whose max_loaded_at changed since the last "
            "successful run of this job; nothing when none did."
        ),
    )
    def build_fresher_job() -> None:
        build_fresher()

    schedule = ScheduleDefinition(
        name=f"schedule__{project_name}__source_freshness",
        job=source_freshness,
        cron_schedule=FRESHNESS_CRON,
        default_status=DefaultScheduleStatus.RUNNING if run_by_default else DefaultScheduleStatus.STOPPED,
    )

    @sensor(
        name=f"sensor__{project_name}__source_freshness",
        job=build_fresher_job,
        minimum_interval_seconds=SENSOR_INTERVAL_SECONDS,
        default_status=DefaultSensorStatus.RUNNING if run_by_default else DefaultSensorStatus.STOPPED,
    )
    def source_freshness_sensor(context: SensorEvaluationContext) -> RunRequest | SkipReason:
        if is_running(context.instance, build_fresher_name):
            return SkipReason(f"a run of {build_fresher_name} is in progress")
        changed = fresher_sources(context.instance, source_asset_keys, build_fresher_name)
        if not changed:
            return SkipReason(f"no source got fresher since the last successful {build_fresher_name}")
        context.log.info(f"{len(changed)} sources got fresher: {sorted(changed)}")
        # Once per change set: a failed run is not relaunched until a source moves again.
        return RunRequest(run_key="|".join(f"{uid}@{ts}" for uid, ts in sorted(changed.items())))

    return Definitions(
        jobs=[source_freshness, build_fresher_job],
        schedules=[schedule],
        sensors=[source_freshness_sensor],
    )
