"""Offline tests of DataMeshDbtProjectComponent.get_cli_args (src/orchestrator/locations/dbt/shared.py).

A stand-in multi-asset with one check, subsettable like the dbt one, records what the override
returns in a run of each kind of asset job. dagster-dbt's own get_cli_args resolves the
component's `cli_args` only during a component load, so the test replaces it with fixed args.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from dagster import (
    AssetCheckResult,
    AssetCheckSpec,
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    AssetSpec,
    Definitions,
    MaterializeResult,
    define_asset_job,
    multi_asset,
)
from dagster_dbt import DbtProject, DbtProjectComponent

from orchestrator.locations.dbt.shared import DataMeshDbtProjectComponent

MODEL = AssetKey(["dbt_example", "models", "02_stg", "knmi", "stg__knmi__climate_hourly"])


def cli_args_in_run(component: DataMeshDbtProjectComponent, selection: AssetSelection) -> list[str]:
    """What the override returns inside a run of an asset job over `selection`."""
    seen: list[list[str]] = []

    @multi_asset(
        specs=[AssetSpec(MODEL, skippable=True)],
        check_specs=[AssetCheckSpec("not_null", asset=MODEL)],
        can_subset=True,
    )
    def dbt_assets(context: AssetExecutionContext) -> Iterator[MaterializeResult | AssetCheckResult]:
        seen.append(component.get_cli_args(context))
        if context.selected_asset_keys:
            yield MaterializeResult(asset_key=MODEL)
        for check_key in context.selected_asset_check_keys:
            yield AssetCheckResult(asset_key=MODEL, check_name=check_key.name, passed=True)

    job = Definitions(assets=[dbt_assets], jobs=[define_asset_job("run", selection)]).resolve_job_def("run")
    assert job.execute_in_process().success
    (args,) = seen
    return args


@pytest.mark.parametrize(
    ("selection", "configured", "expected"),
    [
        pytest.param(AssetSelection.all(), ["build"], ["build"], id="build_all: assets and checks"),
        pytest.param(AssetSelection.all().without_checks(), ["build"], ["build"], id="run_all, seed_all: assets"),
        pytest.param(AssetSelection.all_asset_checks(), ["build"], ["test"], id="test_all: checks only"),
        pytest.param(
            AssetSelection.all_asset_checks(),
            ["build", "--vars", "{day: 1}"],
            ["test", "--vars", "{day: 1}"],
            id="checks only keep the other args",
        ),
        pytest.param(AssetSelection.all_asset_checks(), ["run"], ["run"], id="checks only of another command"),
    ],
)
def test_a_run_of_checks_only_runs_dbt_test(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection: AssetSelection,
    configured: list[str],
    expected: list[str],
) -> None:
    def configured_cli_args(self: DbtProjectComponent, context: AssetExecutionContext) -> list[str]:
        return configured

    monkeypatch.setattr(DbtProjectComponent, "get_cli_args", configured_cli_args)
    # DbtProject wants a dbt_project.yml; nothing else is read here.
    (tmp_path / "dbt_project.yml").write_text("name: dbt_example\n")
    component = DataMeshDbtProjectComponent(project=DbtProject(project_dir=tmp_path))
    assert cli_args_in_run(component, selection) == expected
