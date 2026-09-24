"""Dagster code location `dlt`: every dlt load under dlt_pipelines/pipelines/ingest.

Each source folder carries a defs.yaml (dagster_dlt.DltLoadCollectionComponent) that turns the
module-level dlt `source` and `pipeline` objects into Dagster assets. This module only loads
that component tree and adds one convenience job for the Launchpad.
"""

from pathlib import Path

from dagster import AssetSelection, ComponentTree, Definitions, define_asset_job

import dlt_pipelines as _dlt_pipelines

# src/orchestrator/locations/dlt/definitions.py -> repository root
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _build_defs() -> Definitions:
    loaded = ComponentTree.from_module(defs_module=_dlt_pipelines, project_root=_PROJECT_ROOT).build_defs()
    job_all = define_asset_job(
        name="job_dlt_ingest_all",
        selection=AssetSelection.key_prefixes(["dlt", "ingest"]),
        description="Run every dlt ingest pipeline.",
    )
    return Definitions.merge(loaded, Definitions(jobs=[job_all]))


defs = _build_defs()
