"""Dagster code location for the dbt_example project (see locations/dbt/shared.py)."""

from orchestrator.locations.dbt.dbt_example import defs as _defs_module
from orchestrator.locations.dbt.shared import build_dbt_defs

defs = build_dbt_defs("dbt_example", _defs_module)
