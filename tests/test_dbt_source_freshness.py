"""Offline tests of the source-freshness chain (src/orchestrator/locations/dbt/source_freshness.py).

The job and the sensor meet in the event log; an ephemeral instance holds it here.
"""

import json
from pathlib import Path

import pytest
from dagster import (
    AssetKey,
    AssetObservation,
    DagsterInstance,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    Definitions,
    SensorResult,
    SkipReason,
    build_sensor_context,
)
from dagster_dbt import DbtCliResource, DbtProject

from orchestrator.locations.dbt.shared import dbt_command_job
from orchestrator.locations.dbt.source_freshness import (
    FRESHNESS_METADATA,
    SELECTOR_CONFIG,
    build_source_freshness_defs,
    dbt_selector,
    diff_freshness,
    freshness_observations,
    observed_freshness,
)

KNMI = "source.dbt_example.knmi.climate_hourly"
OTHER = "source.dbt_example.other.table"
KNMI_KEY = AssetKey(["dlt", "ingest", "knmi", "climate_hourly"])


def test_first_tick_sees_every_source_as_fresher() -> None:
    diff = diff_freshness([{"unique_id": KNMI, "max_loaded_at": "2026-09-28T06:00:00"}], {})
    assert diff.changed == {KNMI: "2026-09-28T06:00:00"}
    assert diff.cursor == {KNMI: "2026-09-28T06:00:00"}


def test_unchanged_source_is_not_fresher() -> None:
    previous = {KNMI: "2026-09-28T06:00:00"}
    diff = diff_freshness([{"unique_id": KNMI, "max_loaded_at": "2026-09-28T06:00:00"}], previous)
    assert diff.changed == {}
    assert diff.cursor == previous


def test_advanced_source_is_fresher_and_moves_the_cursor() -> None:
    results = [{"unique_id": KNMI, "max_loaded_at": "2026-09-28T07:00:00"}]
    diff = diff_freshness(results, {KNMI: "2026-09-28T06:00:00"})
    assert diff.changed == {KNMI: "2026-09-28T07:00:00"}
    assert diff.cursor == {KNMI: "2026-09-28T07:00:00"}


def test_source_without_timestamp_keeps_its_cursor() -> None:
    # dbt could not query it (runtime error): neither new data nor a lost timestamp.
    previous = {KNMI: "2026-09-28T06:00:00"}
    diff = diff_freshness([{"unique_id": KNMI, "max_loaded_at": None, "status": "runtime error"}], previous)
    assert diff.changed == {}
    assert diff.cursor == previous


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
    (observation,) = freshness_observations(results, {KNMI: KNMI_KEY})
    assert observation.asset_key == KNMI_KEY
    assert observation.metadata[FRESHNESS_METADATA].value == "2026-09-28T06:00:00"


def test_the_sensor_reads_the_latest_observation_of_each_source() -> None:
    instance = DagsterInstance.ephemeral()
    assert observed_freshness(instance, {KNMI: KNMI_KEY}) == []
    for max_loaded_at in ("2026-09-28T06:00:00", "2026-09-28T07:00:00"):
        instance.report_runless_asset_event(AssetObservation(KNMI_KEY, metadata={FRESHNESS_METADATA: max_loaded_at}))
    assert observed_freshness(instance, {KNMI: KNMI_KEY}) == [
        {"unique_id": KNMI, "max_loaded_at": "2026-09-28T07:00:00"}
    ]
    # An observation from elsewhere, without the metadata, leaves the source out (it keeps its cursor).
    instance.report_runless_asset_event(AssetObservation(KNMI_KEY, metadata={"rows": 3}))
    assert observed_freshness(instance, {KNMI: KNMI_KEY}) == []


def test_dbt_command_job_names_follow_the_convention() -> None:
    job = dbt_command_job("dbt_example", "test_all", ["test"], "dbt test")
    assert job.name == "job__dbt_example__test_all"
    assert [node.name for node in job.graph.nodes] == ["op__dbt_example__test_all"]


def _freshness_defs(project_dir: Path, run_by_default: bool = False) -> Definitions:
    # DbtProject wants a dbt_project.yml, DbtCliResource a profiles.yml; neither is read here.
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "dbt_project.yml").write_text("name: dbt_example\n")
    (project_dir.parent / "profiles.yml").write_text("default: {}\n")
    project = DbtProject(project_dir=project_dir, profiles_dir=project_dir.parent)
    freshness = build_source_freshness_defs(
        project_name="dbt_example",
        project=project,
        source_asset_keys={KNMI: KNMI_KEY},
        run_by_default=run_by_default,
    )
    # build_dbt_defs() registers the `dbt` resource the ops take; the test does the same.
    return Definitions.merge(freshness, Definitions(resources={"dbt": DbtCliResource(project)}))


def test_freshness_definitions_follow_the_convention(tmp_path: Path) -> None:
    repo = _freshness_defs(tmp_path / "dbt_example").get_repository_def()
    job_names = {job.name for job in repo.get_all_jobs()}
    assert {"job__dbt_example__source_freshness", "job__dbt_example__build_fresher"} <= job_names
    (schedule,) = repo.schedule_defs
    assert schedule.name == "schedule__dbt_example__source_freshness"
    assert (schedule.cron_schedule, schedule.job_name) == ("0 * * * *", "job__dbt_example__source_freshness")
    (sensor,) = repo.sensor_defs
    assert (sensor.name, sensor.minimum_interval_seconds) == ("sensor__dbt_example__source_freshness", 300)


def test_automation_is_off_unless_asked(tmp_path: Path) -> None:
    off = _freshness_defs(tmp_path / "dbt_example", run_by_default=False).get_repository_def()
    assert off.schedule_defs[0].default_status == DefaultScheduleStatus.STOPPED
    assert off.sensor_defs[0].default_status == DefaultSensorStatus.STOPPED
    on = _freshness_defs(tmp_path / "dbt_example", run_by_default=True).get_repository_def()
    assert on.schedule_defs[0].default_status == DefaultScheduleStatus.RUNNING
    assert on.sensor_defs[0].default_status == DefaultSensorStatus.RUNNING


def test_sensor_skips_until_the_freshness_job_ran(tmp_path: Path) -> None:
    sensor = _freshness_defs(tmp_path / "dbt_example").get_repository_def().sensor_defs[0]
    assert isinstance(sensor(build_sensor_context(instance=DagsterInstance.ephemeral())), SkipReason)


def test_sensor_builds_downstream_of_the_fresher_sources_once(tmp_path: Path) -> None:
    instance = DagsterInstance.ephemeral()
    instance.report_runless_asset_event(
        AssetObservation(KNMI_KEY, metadata={FRESHNESS_METADATA: "2026-09-28T06:00:00"})
    )
    sensor = _freshness_defs(tmp_path / "dbt_example").get_repository_def().sensor_defs[0]

    first = sensor(build_sensor_context(instance=instance))
    assert isinstance(first, SensorResult)
    (request,) = first.run_requests or []
    selector = {"config": {SELECTOR_CONFIG: "source:knmi.climate_hourly+"}}
    assert request.run_config == {"ops": {"op__dbt_example__build_fresher": selector}}
    assert not first.asset_events  # the job observes the sources; the sensor only reads
    assert json.loads(first.cursor or "") == {KNMI: "2026-09-28T06:00:00"}

    # The same observation again: nothing got fresher, the cursor stays.
    second = sensor(build_sensor_context(instance=instance, cursor=first.cursor))
    assert isinstance(second, SensorResult)
    assert not second.run_requests
    assert second.cursor == first.cursor
