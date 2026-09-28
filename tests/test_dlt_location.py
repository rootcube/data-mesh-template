"""The dlt code location: its jobs and schedules (src/orchestrator/locations/dlt/definitions.py)."""

from dagster import AssetKey, DefaultScheduleStatus

from orchestrator.locations.dlt.definitions import INGEST_CRON, defs


def test_every_source_folder_gets_its_own_job() -> None:
    job = defs.get_repository_def().get_job("job__dlt__ingest_knmi")
    assert set(job.asset_layer.selected_asset_keys) == {AssetKey(["dlt", "ingest", "knmi", "climate_hourly"])}


def test_every_source_folder_gets_its_own_daily_schedule() -> None:
    schedule = defs.get_repository_def().get_schedule_def("schedule__dlt__ingest_knmi")
    assert (schedule.cron_schedule, schedule.job_name) == (INGEST_CRON, "job__dlt__ingest_knmi")


def test_the_all_sources_schedule_is_an_opt_in() -> None:
    repo = defs.get_repository_def()
    assert "job__dlt__ingest_all" in {job.name for job in repo.get_all_jobs()}
    schedule = repo.get_schedule_def("schedule__dlt__ingest_all")
    assert (schedule.cron_schedule, schedule.job_name) == (INGEST_CRON, "job__dlt__ingest_all")
    assert schedule.default_status == DefaultScheduleStatus.STOPPED
