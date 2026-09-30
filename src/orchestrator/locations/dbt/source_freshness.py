"""The source-freshness chain of one dbt location: check every hour, rebuild what got fresher.

`job__<location>__source_freshness` runs `dbt source freshness` (its schedule fires every hour)
and records what dbt found as one asset observation per source, `max_loaded_at` in its metadata.
`sensor__<location>__source_freshness` reads each source's latest observation every five minutes,
compares its `max_loaded_at` with the value in its cursor and, when any advanced, launches
`job__<location>__build_fresher`: `dbt build --select source:<source>.<table>+ ...`, the
downstream of exactly the sources that changed. A source takes part when its YAML carries a
`freshness` block and a `loaded_at_field` (or `loaded_at_query`); dbt skips the others.

The hand-off between the job and the sensor is the Dagster event log, not dbt's `sources.json`:
the job may run in its own pod (Kubernetes), the sensor in the code server, and the event log is
the instance storage both share (Postgres there, SQLite under `dagster dev`).
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dagster import (
    AssetKey,
    AssetObservation,
    DagsterInstance,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    Definitions,
    OpExecutionContext,
    RunRequest,
    ScheduleDefinition,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    job,
    op,
    sensor,
)
from dagster_dbt import DbtCliResource, DbtProject

FRESHNESS_CRON = "0 * * * *"  # dbt source freshness, every hour on the hour
SENSOR_INTERVAL_SECONDS = 300  # the sensor re-reads the observations every five minutes
SELECTOR_CONFIG = "sources_selector"  # op config of build_fresher: the dbt --select string
FRESHNESS_METADATA = "max_loaded_at"  # the observation metadata the job writes and the sensor reads


@dataclass(frozen=True)
class FreshnessDiff:
    """The sources whose `max_loaded_at` advanced since the previous tick, and the next cursor."""

    changed: dict[str, str]  # unique_id -> max_loaded_at
    cursor: dict[str, str]  # unique_id -> max_loaded_at for every source dbt could query


def diff_freshness(results: Iterable[Mapping[str, Any]], previous: Mapping[str, str]) -> FreshnessDiff:
    """Compare the `results` of a sources.json with the `previous` cursor.

    A source without `max_loaded_at` (dbt could not query it) keeps its previous value, so a
    transient error never looks like new data and never loses the last known timestamp.
    """
    cursor = dict(previous)
    changed: dict[str, str] = {}
    for result in results:
        unique_id = result.get("unique_id") or ""
        max_loaded_at = result.get("max_loaded_at")
        if not unique_id or not max_loaded_at:
            continue
        cursor[unique_id] = max_loaded_at
        if max_loaded_at != previous.get(unique_id):
            changed[unique_id] = max_loaded_at
    return FreshnessDiff(changed=changed, cursor=cursor)


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


def observed_freshness(instance: DagsterInstance, source_asset_keys: Mapping[str, AssetKey]) -> list[dict[str, str]]:
    """The latest `max_loaded_at` observed per source, in the shape of sources.json results.

    A source whose latest observation carries no `max_loaded_at` (never checked, or observed by
    something else) is left out, so it keeps its cursor value.
    """
    results = []
    for unique_id, asset_key in source_asset_keys.items():
        records = instance.fetch_observations(asset_key, limit=1).records
        observation = records[0].asset_observation if records else None
        value = observation.metadata.get(FRESHNESS_METADATA) if observation else None
        if value is not None:
            results.append({"unique_id": unique_id, "max_loaded_at": str(value.value)})
    return results


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
    project: DbtProject,
    source_asset_keys: Mapping[str, AssetKey],
    run_by_default: bool,
) -> Definitions:
    """The two jobs, the schedule and the sensor of the chain, named after the location.

    `source_asset_keys` maps a source's unique_id to its Dagster asset key; the freshness job
    records its observations on those assets, and the sensor reads them back. `run_by_default` decides whether
    the schedule and the sensor start running when the location loads (off in personal
    environments, where nothing should fire by itself).
    """
    freshness_dir = Path(project.project_dir) / project.target_path / "freshness"
    sources_json = freshness_dir / "sources.json"
    build_fresher_op = f"op__{project_name}__build_fresher"

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

    @op(name=build_fresher_op, config_schema={SELECTOR_CONFIG: str})
    def build_fresher(context: OpExecutionContext, dbt: DbtCliResource) -> None:
        """`dbt build --select <sources_selector>`."""
        selector: str = context.op_config[SELECTOR_CONFIG]
        dbt.cli(["build", "--select", selector], context=context).wait()

    @job(
        name=f"job__{project_name}__build_fresher",
        description=(
            f"dbt build downstream of the {project_name} sources that got fresher; from the Launchpad, "
            f"any dbt selector goes in {SELECTOR_CONFIG}."
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
    def source_freshness_sensor(context: SensorEvaluationContext) -> SensorResult | SkipReason:
        results = observed_freshness(context.instance, source_asset_keys)
        if not results:
            return SkipReason(f"no freshness observations yet: {source_freshness.name} has not run")
        previous: dict[str, str] = json.loads(context.cursor) if context.cursor else {}
        diff = diff_freshness(results, previous)
        context.log.info(f"{len(diff.changed)} of {len(results)} sources got fresher: {sorted(diff.changed)}")
        if not diff.changed:
            return SensorResult(skip_reason=SkipReason("no source got fresher"), cursor=json.dumps(diff.cursor))
        run_key = "|".join(f"{uid}@{ts}" for uid, ts in sorted(diff.changed.items()))
        run_config = {"ops": {build_fresher_op: {"config": {SELECTOR_CONFIG: dbt_selector(diff.changed)}}}}
        return SensorResult(
            run_requests=[RunRequest(run_key=run_key, run_config=run_config)], cursor=json.dumps(diff.cursor)
        )

    return Definitions(
        jobs=[source_freshness, build_fresher_job],
        schedules=[schedule],
        sensors=[source_freshness_sensor],
    )
