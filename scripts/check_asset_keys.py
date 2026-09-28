#!/usr/bin/env python3
"""Check the dlt -> dbt asset key contract between the Dagster code locations.

Code locations never import each other, so cross-location lineage rests entirely on shared asset
keys: a dbt source declares `config.meta.dagster.asset_key` equal to the key of the dlt asset that
loads it (`dlt/ingest/<source>/<entity>`). A typo on either side splits the graph in two without
breaking anything a parse, a `dagster definitions validate` or a test would notice.

This loads every code location in workspace.yaml and compares the `dlt/` keys:

- a `dlt/` key another location declares that the dlt location does not produce: error
- a dlt asset no other location declares: warning, since a source may simply be unused

Usage: uv run python scripts/check_asset_keys.py
"""

import importlib
import sys
from pathlib import Path

import yaml
from dagster import AssetKey

# scripts/check_asset_keys.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace.yaml"
# The code location that produces the dlt assets, and the first segment of every key it produces.
DLT_LOCATION = "dlt"


def location_modules(workspace_path: Path) -> dict[str, str]:
    """Location name -> module name, exactly as workspace.yaml lists them."""
    workspace = yaml.safe_load(workspace_path.read_text(encoding="utf-8")) or {}
    locations = {}
    for entry in workspace.get("load_from", []):
        module = entry.get("python_module", {})
        locations[module.get("location_name") or module["module_name"]] = module["module_name"]
    return locations


def asset_keys(module_name: str) -> set[AssetKey]:
    """Every asset key a code location declares, external ones (dbt sources) included."""
    defs = importlib.import_module(module_name).defs
    return set(defs.resolve_all_asset_keys())


def dlt_keys(keys: set[AssetKey]) -> list[AssetKey]:
    """The keys under the dlt location's prefix, sorted."""
    return sorted((key for key in keys if key.path[:1] == [DLT_LOCATION]), key=lambda key: key.path)


def declared_dlt_keys(keys_by_location: dict[str, set[AssetKey]]) -> set[AssetKey]:
    """Every `dlt/` key a location other than the dlt one declares (the dbt sources)."""
    return {key for name, keys in keys_by_location.items() if name != DLT_LOCATION for key in dlt_keys(keys)}


def contract_problems(keys_by_location: dict[str, set[AssetKey]]) -> tuple[list[str], list[str]]:
    """Errors and warnings on the `dlt/` keys shared between the locations."""
    produced = keys_by_location[DLT_LOCATION]
    errors, warnings = [], []

    for location, keys in sorted(keys_by_location.items()):
        if location == DLT_LOCATION:
            continue
        for key in dlt_keys(keys):
            if key not in produced:
                errors.append(f"{location} declares '{key.to_user_string()}', which the dlt location does not produce")

    for key in sorted(produced - declared_dlt_keys(keys_by_location), key=lambda key: key.path):
        warnings.append(f"no location declares the dlt asset '{key.to_user_string()}' (an unused source?)")

    return errors, warnings


def main() -> int:
    locations = location_modules(WORKSPACE)
    if DLT_LOCATION not in locations:
        print(f"no '{DLT_LOCATION}' code location in {WORKSPACE.name}, nothing to check")
        return 1

    keys_by_location = {name: asset_keys(module) for name, module in locations.items()}
    errors, warnings = contract_problems(keys_by_location)

    for warning in warnings:
        print(f" warning: {warning}")
    for error in errors:
        print(f" error: {error}")

    if errors:
        produced = sorted(k.to_user_string() for k in keys_by_location[DLT_LOCATION])
        print(f"\nThe dlt location produces: {', '.join(produced) or '(none)'}")
        print("Fix the `config.meta.dagster.asset_key` in the dbt source YAML, or the dlt table name.")
        return 1

    matched = declared_dlt_keys(keys_by_location)
    print(f" asset key contract ok: {len(matched)} dlt key(s) declared across {len(keys_by_location)} code locations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
