"""Factory for dbt code locations: one Dagster code location per dbt project.

Every project folder under src/orchestrator/locations/dbt/<project>/ holds a definitions.py that
calls build_dbt_defs() and a defs/dbt/defs.yaml with the DataMeshDbtProjectComponent
configuration for that project. Adding a project means adding such a folder and one entry in
workspace.yaml (one dbt project per mesh node); the projects never import each other,
cross-project lineage resolves through shared asset keys (dbt sources with
`config.meta.dagster.asset_key`).

Asset keys mirror the repository layout so the Dagster UI groups assets by project, package,
layer and domain: `<project>/models/02_stg/knmi/stg__knmi__climate_hourly`, or
`<project>/packages/dbt_common/models/04_mrt/common/dim__common__calendar` for a model that
comes from a package. The group is the key without its last segment.
"""

import json
from collections.abc import Mapping, Sequence
from functools import cached_property
from pathlib import Path
from types import ModuleType
from typing import Any

from dagster import (
    AssetKey,
    AssetSelection,
    AssetSpec,
    ComponentLoadContext,
    ComponentTree,
    Definitions,
    JobDefinition,
    OpExecutionContext,
    define_asset_job,
    job,
    op,
)
from dagster_dbt import DbtCliResource
from dagster_dbt.asset_utils import get_node
from dagster_dbt.components.dbt_project.component import DbtProjectComponent, DbtProjectComponentTranslator

from orchestrator.locations.dbt.source_freshness import build_source_freshness_defs
from orchestrator.resources.snowflake import SnowflakeSettings

# src/orchestrator/locations/dbt/shared.py -> repository root
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def compute_asset_key(node: Mapping[str, Any], project_name: str) -> AssetKey:
    """Asset key of a dbt node: `<project>/<path segments>/<name>`.

    `meta.dagster.asset_key` (or `config.meta.dagster.asset_key`) wins when set; the dbt sources
    use it to take the key of the dlt asset that loads them. Otherwise the key follows the file
    path: `models/02_stg/knmi/foo.sql` in `dbt_example` becomes
    `dbt_example/models/02_stg/knmi/foo`, and a node from an installed package gets
    `<project>/packages/<package>/...` in front of its own path. Sources without an override are
    keyed `<project>/sources/<source name>/<table>`.
    """
    meta = (node.get("meta") or {}).get("dagster") or {}
    config_meta = ((node.get("config") or {}).get("meta") or {}).get("dagster") or {}
    override = config_meta.get("asset_key") or meta.get("asset_key")
    if override:
        return AssetKey(list(override))

    package = node.get("package_name") or ""
    prefix = [project_name] if package == project_name else [project_name, "packages", package]
    if node.get("resource_type") == "source":
        return AssetKey([*prefix, "sources", node.get("source_name") or "", node.get("name") or ""])

    # dbt writes the path with the OS separator, so a manifest parsed on Windows has backslashes.
    segments = (node.get("original_file_path") or "").replace("\\", "/").split("/")
    dirs = segments[2:-1] if segments[0] == "packages" else segments[:-1]
    return AssetKey([*prefix, *dirs, node.get("name") or ""])


def compute_group_name(key: AssetKey) -> str:
    """Group of a dbt asset: its key without the last segment.

    A one-segment key (a `meta.dagster.asset_key` override with a single element) leaves nothing
    to group by, and Dagster rejects an empty group name, so that key groups under itself.
    """
    return "/".join(key.path[:-1]) or key.path[0]


class DataMeshDbtTranslator(DbtProjectComponentTranslator):
    """Keys from the file path, groups from the key, `kinds` from the materialization."""

    def get_asset_spec(self, manifest: Mapping[str, Any], unique_id: str, project: Any) -> AssetSpec:
        spec = super().get_asset_spec(manifest, unique_id, project)
        node = get_node(manifest, unique_id)
        project_name = (manifest.get("metadata") or {}).get("project_name") or ""
        key = compute_asset_key(node, project_name)
        materialized = (node.get("config") or {}).get("materialized")
        kinds = {"dbt", materialized} if materialized else {"dbt"}
        return spec.replace_attributes(key=key, group_name=compute_group_name(key), kinds=kinds)


class DataMeshDbtProjectComponent(DbtProjectComponent):
    """DbtProjectComponent with the data mesh key and group scheme (the `type:` of defs.yaml)."""

    @cached_property
    def translator(self) -> DbtProjectComponentTranslator:
        return DataMeshDbtTranslator(self, self.translation_settings)

    def build_defs_from_state(self, context: ComponentLoadContext, state_path: Path | None) -> Definitions:
        """Build the assets from the project on disk, never from the `.local_defs_state` snapshot.

        dagster-dbt copies the project into `.local_defs_state/` and, whenever that snapshot exists,
        builds the assets from the copy; it only refreshes it under `dagster dev`. Everything else
        (`dagster definitions validate`) would then validate a snapshot instead of the models on
        disk. Ignoring the snapshot costs nothing: the dev-time refresh runs `dbt parse` against the
        real project dir, so `dbt/<project>/target/manifest.json` is what both paths read.
        """
        return super().build_defs_from_state(context, state_path=None)


def dbt_command_job(project_name: str, name: str, args: Sequence[str], description: str) -> JobDefinition:
    """`job__<project>__<name>`: one op that runs `dbt <args>` on the whole project."""

    @op(name=f"op__{project_name}__{name}")
    def run_dbt(context: OpExecutionContext, dbt: DbtCliResource) -> None:
        dbt.cli(list(args), context=context).wait()

    @job(name=f"job__{project_name}__{name}", description=description)
    def run_job() -> None:
        run_dbt()

    return run_job


def source_asset_keys(manifest_path: Path, project_name: str) -> dict[str, AssetKey]:
    """Asset key per dbt source unique_id, read from the manifest with the scheme of compute_asset_key."""
    sources: Mapping[str, Any] = json.loads(manifest_path.read_text()).get("sources") or {}
    return {unique_id: compute_asset_key(node, project_name) for unique_id, node in sources.items()}


def build_dbt_defs(project_name: str, defs_module: ModuleType) -> Definitions:
    """Load the component tree of one dbt project and add its jobs, schedule and sensor.

    Definitions are named `<kind>__<location>__<name>`, the location being the project:
    `job__dbt_example__build_all` (the assets), `run_all`, `test_all` and `seed_all` (one dbt
    command each), and the source-freshness chain of `source_freshness.py`. The ops share one
    `dbt` resource pointed at the component's project, so every job runs the same project with
    the same profiles.
    """
    tree = ComponentTree.from_module(defs_module=defs_module, project_root=PROJECT_ROOT)
    loaded = tree.build_defs()
    components = tree.get_all_components(of_type=DataMeshDbtProjectComponent)
    if len(components) != 1:
        raise ValueError(f"{project_name}: expected one DataMeshDbtProjectComponent, found {len(components)}")
    project = components[0].dbt_project

    jobs = [
        define_asset_job(
            name=f"job__{project_name}__build_all",
            selection=AssetSelection.all(),
            description=f"dbt build for the whole {project_name} project, asset by asset.",
        ),
        dbt_command_job(project_name, "run_all", ["run"], f"dbt run for the whole {project_name} project: no tests."),
        dbt_command_job(project_name, "test_all", ["test"], f"dbt test for the whole {project_name} project."),
        dbt_command_job(project_name, "seed_all", ["seed"], f"dbt seed for the whole {project_name} project."),
    ]
    freshness = build_source_freshness_defs(
        project_name=project_name,
        project=project,
        source_asset_keys=source_asset_keys(project.manifest_path, project_name),
        run_by_default=not SnowflakeSettings.from_env().is_personal,
    )
    return Definitions.merge(loaded, Definitions(jobs=jobs, resources={"dbt": DbtCliResource(project)}), freshness)
