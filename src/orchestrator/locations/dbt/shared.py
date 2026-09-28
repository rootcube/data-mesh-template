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

from collections.abc import Mapping
from functools import cached_property
from pathlib import Path
from types import ModuleType
from typing import Any

from dagster import (
    AssetKey,
    AssetSelection,
    AssetSpec,
    AutomationCondition,
    ComponentLoadContext,
    ComponentTree,
    Definitions,
    define_asset_job,
)
from dagster_dbt.asset_utils import get_node
from dagster_dbt.components.dbt_project.component import DbtProjectComponent, DbtProjectComponentTranslator

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

    # `original_file_path` is relative to the node's own package, so a package node carries its own
    # path and nothing else. dbt writes it with the OS separator, so a manifest parsed on Windows
    # has backslashes.
    segments = (node.get("original_file_path") or "").replace("\\", "/").split("/")
    return AssetKey([*prefix, *segments[:-1], node.get("name") or ""])


def compute_group_name(key: AssetKey) -> str:
    """Group of a dbt asset: its key without the last segment.

    A one-segment key (a `meta.dagster.asset_key` override with a single element) leaves nothing
    to group by, and Dagster rejects an empty group name, so that key groups under itself.
    """
    return "/".join(key.path[:-1]) or key.path[0]


class DataMeshDbtTranslator(DbtProjectComponentTranslator):
    """Keys from the file path, groups from the key, `kinds` from the materialization.

    Every dbt asset also carries `AutomationCondition.eager()`: a model rebuilds as soon as the
    asset feeding its source has been loaded, without a schedule per layer. Dagster puts the
    condition to work through the `default_automation_condition_sensor` of the code location, which
    ships stopped, so nothing runs on its own in dev; turn it on under Automation in the UI.
    """

    def get_asset_spec(self, manifest: Mapping[str, Any], unique_id: str, project: Any) -> AssetSpec:
        spec = super().get_asset_spec(manifest, unique_id, project)
        node = get_node(manifest, unique_id)
        project_name = (manifest.get("metadata") or {}).get("project_name") or ""
        key = compute_asset_key(node, project_name)
        materialized = (node.get("config") or {}).get("materialized")
        kinds = {"dbt", materialized} if materialized else {"dbt"}
        return spec.replace_attributes(
            key=key,
            group_name=compute_group_name(key),
            kinds=kinds,
            automation_condition=AutomationCondition.eager(),
        )


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


def build_dbt_defs(project_name: str, defs_module: ModuleType) -> Definitions:
    """Load the component tree of one dbt project and add a build-everything job.

    `project_name` only names the job; the asset keys carry the project name the manifest reports.
    A mismatch would ship a job whose name lies about what it builds, so it fails here instead.
    """
    loaded = ComponentTree.from_module(defs_module=defs_module, project_root=PROJECT_ROOT).build_defs()
    keys = loaded.resolve_all_asset_keys()
    if not any(key.path[0] == project_name for key in keys):
        raise ValueError(
            f"build_dbt_defs({project_name!r}) in this location's definitions.py builds no asset under "
            f"{project_name!r}; the dbt project named in defs/dbt/defs.yaml produces "
            f"{sorted({key.path[0] for key in keys})}."
        )
    job_all = define_asset_job(
        name=f"job_{project_name}_build_all",
        # This component's assets, not AssetSelection.all(): a Python asset merged into the same
        # location (docs: Development > Adding Python assets) must not silently join the dbt build.
        # Intersecting with all() drops the stub assets dagster-dbt adds for dbt sources, which are
        # not materializable here and would make the job fail to resolve.
        selection=AssetSelection.assets(*keys) & AssetSelection.all(),
        description=f"dbt build for the whole {project_name} project.",
    )
    return Definitions.merge(loaded, Definitions(jobs=[job_all]))
