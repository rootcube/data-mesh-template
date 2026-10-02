"""Offline tests of the source-freshness chain (src/orchestrator/locations/dbt/source_freshness.py).

The jobs and the sensor meet in the event log and the run history; an ephemeral instance holds
both here. A stand-in job named like `build_fresher` makes its runs, and where the real one runs,
a fake `DbtCliResource.cli()` stands in for dbt.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from dagster import (
    AssetKey,
    AssetMaterialization,
    AssetObservation,
    DagsterInstance,
    DagsterRunStatus,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    Definitions,
    RunRequest,
    SkipReason,
    build_sensor_context,
    job,
    op,
)
from dagster_dbt import DbtCliResource, DbtProject, DbtProjectComponent

from orchestrator.locations.dbt.source_freshness import (
    FRESHNESS_METADATA,
    IN_PROGRESS,
    build_source_freshness_defs,
    dbt_selector,
    diff_freshness,
    fresher_sources,
    freshness_observations,
    observed_freshness,
)

KNMI = "source.dbt_example.knmi.climate_hourly"
OTHER = "source.dbt_example.other.table"
KNMI_KEY = AssetKey(["dlt", "ingest", "knmi", "climate_hourly"])
STG_KEY = AssetKey(["dbt_example", "models", "02_stg", "knmi", "stg__knmi__climate_hourly"])
SOURCES = {KNMI: KNMI_KEY}
BUILD_FRESHER = "job__dbt_example__build_fresher"


@op
def build() -> None: ...


@op
def fail() -> None:
    raise RuntimeError("dbt build failed")


@job(name=BUILD_FRESHER)
def succeeding_build() -> None:
    build()


@job(name=BUILD_FRESHER)
def failing_build() -> None:
    fail()


def observe(instance: DagsterInstance, max_loaded_at: str) -> None:
    """What job__<location>__source_freshness records when dbt finds `max_loaded_at`."""
    instance.report_runless_asset_event(AssetObservation(KNMI_KEY, metadata={FRESHNESS_METADATA: max_loaded_at}))


def test_every_source_is_fresher_without_a_previous_value() -> None:
    results = [{"unique_id": KNMI, "max_loaded_at": "2026-09-28T06:00:00"}]
    assert diff_freshness(results, {}) == {KNMI: "2026-09-28T06:00:00"}


def test_unchanged_source_is_not_fresher() -> None:
    results = [{"unique_id": KNMI, "max_loaded_at": "2026-09-28T06:00:00"}]
    assert diff_freshness(results, {KNMI: "2026-09-28T06:00:00"}) == {}


def test_advanced_source_is_fresher() -> None:
    results = [{"unique_id": KNMI, "max_loaded_at": "2026-09-28T07:00:00"}]
    assert diff_freshness(results, {KNMI: "2026-09-28T06:00:00"}) == {KNMI: "2026-09-28T07:00:00"}


def test_source_without_timestamp_is_not_fresher() -> None:
    # dbt could not query it (runtime error): that is no new data.
    results = [{"unique_id": KNMI, "max_loaded_at": None, "status": "runtime error"}]
    assert diff_freshness(results, {KNMI: "2026-09-28T06:00:00"}) == {}


def test_selector_covers_the_downstream_of_each_source() -> None:
    assert dbt_selector([KNMI, OTHER]) == "source:knmi.climate_hourly+ source:other.table+"


def test_selector_rejects_a_model_unique_id() -> None:
    with pytest.raises(ValueError):
        dbt_selector(["model.dbt_example.stg__knmi__climate_hourly"])


def test_the_job_observes_every_source_dbt_could_query() -> None:
    results = [
        {"unique_id": KNMI, "max_loaded_at": "2026-09-28T06:00:00", "status": "pass"},
        {"unique_id": OTHER, "max_loaded_at": "2026-09-28T05:00:00", "status": "pass"},  # no asset key
        {"unique_id": KNMI, "max_loaded_at": None, "status": "runtime error"},
    ]
    (observation,) = freshness_observations(results, SOURCES)
    assert observation.asset_key == KNMI_KEY
    assert observation.metadata[FRESHNESS_METADATA].value == "2026-09-28T06:00:00"


def test_the_latest_observation_of_each_source_is_read_back() -> None:
    instance = DagsterInstance.ephemeral()
    assert observed_freshness(instance, SOURCES) == []
    observe(instance, "2026-09-28T06:00:00")
    observe(instance, "2026-09-28T07:00:00")
    assert observed_freshness(instance, SOURCES) == [{"unique_id": KNMI, "max_loaded_at": "2026-09-28T07:00:00"}]
    # An observation from elsewhere, without the metadata, leaves the source out.
    instance.report_runless_asset_event(AssetObservation(KNMI_KEY, metadata={"rows": 3}))
    assert observed_freshness(instance, SOURCES) == []


def test_fresher_is_measured_from_the_last_successful_build() -> None:
    instance = DagsterInstance.ephemeral()
    assert fresher_sources(instance, SOURCES, BUILD_FRESHER) == {}  # never checked
    observe(instance, "2026-09-28T06:00:00")
    assert fresher_sources(instance, SOURCES, BUILD_FRESHER) == {KNMI: "2026-09-28T06:00:00"}  # never built

    succeeding_build.execute_in_process(instance=instance)
    assert fresher_sources(instance, SOURCES, BUILD_FRESHER) == {}  # built from 06:00
    observe(instance, "2026-09-28T06:00:00")
    assert fresher_sources(instance, SOURCES, BUILD_FRESHER) == {}  # checked again, nothing new

    observe(instance, "2026-09-28T07:00:00")
    failing_build.execute_in_process(instance=instance, raise_on_error=False)
    # A failed run moves nothing: the next run builds 07:00 again.
    assert fresher_sources(instance, SOURCES, BUILD_FRESHER) == {KNMI: "2026-09-28T07:00:00"}


def _component(tmp_path: Path) -> DbtProjectComponent:
    # DbtProject wants a dbt_project.yml, DbtCliResource a profiles.yml; neither is read here.
    project_dir = tmp_path / "dbt_example"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "dbt_project.yml").write_text("name: dbt_example\n")
    (tmp_path / "profiles.yml").write_text("default: {}\n")
    return DbtProjectComponent(project=DbtProject(project_dir=project_dir, profiles_dir=tmp_path))


def _freshness_defs(component: DbtProjectComponent, run_by_default: bool = False) -> Definitions:
    freshness = build_source_freshness_defs(
        project_name="dbt_example",
        component=component,
        source_asset_keys=SOURCES,
        run_by_default=run_by_default,
    )
    # build_dbt_defs() registers the `dbt` resource the ops take; the test does the same.
    return Definitions.merge(freshness, Definitions(resources={"dbt": DbtCliResource(component.dbt_project)}))


def test_freshness_definitions_follow_the_convention(tmp_path: Path) -> None:
    repo = _freshness_defs(_component(tmp_path)).get_repository_def()
    job_names = {job.name for job in repo.get_all_jobs()}
    assert {"job__dbt_example__source_freshness", BUILD_FRESHER} <= job_names
    assert [node.name for node in repo.get_job(BUILD_FRESHER).graph.nodes] == ["op__dbt_example__build_fresher"]
    (schedule,) = repo.schedule_defs
    assert schedule.name == "schedule__dbt_example__source_freshness"
    assert (schedule.cron_schedule, schedule.job_name) == ("0 * * * *", "job__dbt_example__source_freshness")
    (sensor,) = repo.sensor_defs
    assert (sensor.name, sensor.minimum_interval_seconds) == ("sensor__dbt_example__source_freshness", 300)
    assert sensor.job_name == BUILD_FRESHER


def test_automation_is_off_unless_asked(tmp_path: Path) -> None:
    off = _freshness_defs(_component(tmp_path), run_by_default=False).get_repository_def()
    assert off.schedule_defs[0].default_status == DefaultScheduleStatus.STOPPED
    assert off.sensor_defs[0].default_status == DefaultSensorStatus.STOPPED
    on = _freshness_defs(_component(tmp_path), run_by_default=True).get_repository_def()
    assert on.schedule_defs[0].default_status == DefaultScheduleStatus.RUNNING
    assert on.sensor_defs[0].default_status == DefaultSensorStatus.RUNNING


def test_sensor_launches_the_build_once_per_change(tmp_path: Path) -> None:
    instance = DagsterInstance.ephemeral()
    sensor = _freshness_defs(_component(tmp_path)).get_repository_def().sensor_defs[0]
    assert isinstance(sensor(build_sensor_context(instance=instance)), SkipReason)  # nothing observed yet

    observe(instance, "2026-09-28T06:00:00")
    request = sensor(build_sensor_context(instance=instance))
    assert isinstance(request, RunRequest)
    # The run decides what to build itself; the run key keeps one change set to one launch.
    assert (request.run_key, request.run_config, request.asset_selection) == (f"{KNMI}@2026-09-28T06:00:00", {}, None)

    succeeding_build.execute_in_process(instance=instance)
    assert isinstance(sensor(build_sensor_context(instance=instance)), SkipReason)  # built


@pytest.mark.parametrize(
    "status",
    [
        DagsterRunStatus.NOT_STARTED,
        DagsterRunStatus.STARTING,
        DagsterRunStatus.STARTED,
        DagsterRunStatus.CANCELING,
    ],
)
def test_sensor_waits_while_a_build_is_in_progress(tmp_path: Path, status: DagsterRunStatus) -> None:
    instance = DagsterInstance.ephemeral()
    sensor = _freshness_defs(_component(tmp_path)).get_repository_def().sensor_defs[0]
    observe(instance, "2026-09-28T06:00:00")  # fresher: without the run, the sensor would launch
    instance.create_run_for_job(succeeding_build, status=status)  # launched by hand, or by an earlier tick
    skip = sensor(build_sensor_context(instance=instance))
    assert isinstance(skip, SkipReason)
    assert skip.skip_message == f"a run of {BUILD_FRESHER} is in progress"


def test_a_queued_build_is_in_progress() -> None:
    # QUEUED is where every launch starts under the default run coordinator. Dagster refuses a queued
    # run without the origin of a deployed code location, so the guard's status list stands in for
    # it; the test above shows the guard skips for every status on that list it can create.
    assert DagsterRunStatus.QUEUED in IN_PROGRESS


@pytest.mark.parametrize("status", [DagsterRunStatus.FAILURE, DagsterRunStatus.CANCELED])
def test_a_finished_build_does_not_hold_the_sensor_back(tmp_path: Path, status: DagsterRunStatus) -> None:
    instance = DagsterInstance.ephemeral()
    sensor = _freshness_defs(_component(tmp_path)).get_repository_def().sensor_defs[0]
    observe(instance, "2026-09-28T06:00:00")
    instance.create_run_for_job(succeeding_build, status=status)
    # It built nothing that counts, so the source is still fresher and the sensor launches.
    assert isinstance(sensor(build_sensor_context(instance=instance)), RunRequest)


@dataclass
class FakeInvocation:
    """What `DbtCliResource.cli()` returns: a stream with a materialization of the model as dbt's result."""

    fail: bool

    def stream(self) -> Iterator[AssetMaterialization]:
        if self.fail:
            raise RuntimeError("dbt build failed")
        yield AssetMaterialization(STG_KEY)


def fake_dbt(monkeypatch: pytest.MonkeyPatch, fail: bool = False) -> list[tuple[list[str], dict[str, Any]]]:
    """Replace `DbtCliResource.cli()` with a fake; the returned list collects the arguments of every call."""
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def cli(self: DbtCliResource, args: Sequence[str], **kwargs: Any) -> FakeInvocation:
        calls.append((list(args), kwargs))
        return FakeInvocation(fail=fail)

    monkeypatch.setattr(DbtCliResource, "cli", cli)
    return calls


def test_build_fresher_builds_the_downstream_of_the_fresher_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_dbt(monkeypatch)
    component = _component(tmp_path)
    build_fresher = _freshness_defs(component).get_repository_def().get_job(BUILD_FRESHER)
    instance = DagsterInstance.ephemeral()

    assert build_fresher.execute_in_process(instance=instance).success
    assert calls == []  # nothing observed, nothing to build

    observe(instance, "2026-09-28T06:00:00")
    result = build_fresher.execute_in_process(instance=instance)
    assert result.success
    ((args, kwargs),) = calls
    assert args == ["build", "--select", "source:knmi.climate_hourly+"]
    # The manifest and translator of the dbt assets, so the results land on their asset keys.
    assert kwargs["manifest"] == component.dbt_project.manifest_path
    assert kwargs["dagster_dbt_translator"] is component.translator
    # dbt's results are events of the run: the model shows as materialized by it.
    (record,) = instance.fetch_materializations(STG_KEY, limit=10).records
    assert record.run_id == result.run_id

    assert build_fresher.execute_in_process(instance=instance).success
    assert len(calls) == 1  # built from 06:00 already


def test_a_failed_build_fresher_builds_the_same_sources_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_dbt(monkeypatch, fail=True)
    build_fresher = _freshness_defs(_component(tmp_path)).get_repository_def().get_job(BUILD_FRESHER)
    instance = DagsterInstance.ephemeral()
    observe(instance, "2026-09-28T06:00:00")

    assert not build_fresher.execute_in_process(instance=instance, raise_on_error=False).success
    assert not build_fresher.execute_in_process(instance=instance, raise_on_error=False).success
    assert [args for args, _ in calls] == [["build", "--select", "source:knmi.climate_hourly+"]] * 2
