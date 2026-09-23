"""Factory for dbt code locations: one Dagster code location per dbt project.

Every project folder under src/orchestrator/locations/dbt/<project>/ holds a definitions.py that
calls build_dbt_defs() and a defs/dbt/defs.yaml with the dagster_dbt.DbtProjectComponent
configuration for that project. Adding a project means adding such a folder and one
entry in workspace.yaml (one dbt project per mesh node); the projects never import each other, cross-project lineage
resolves through shared asset keys (dbt sources with `meta.dagster.asset_key`).
"""

from pathlib import Path
from types import ModuleType

from dagster import AssetSelection, ComponentTree, Definitions, define_asset_job

# src/orchestrator/locations/dbt/shared.py -> repository root
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def build_dbt_defs(project_name: str, defs_module: ModuleType) -> Definitions:
    """Load the component tree of one dbt project and add a build-everything job."""
    loaded = ComponentTree.from_module(defs_module=defs_module, project_root=PROJECT_ROOT).build_defs()
    job_all = define_asset_job(
        name=f"job_{project_name}_build_all",
        selection=AssetSelection.all(),
        description=f"dbt build for the whole {project_name} project.",
    )
    return Definitions.merge(loaded, Definitions(jobs=[job_all]))
