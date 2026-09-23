---
icon: material/language-python
---

# Adding Python assets

Reach for a plain Python asset when neither [dlt](adding-dlt-loads.md) (getting data in) nor
[dbt](adding-dbt-models.md) (transforming it in Snowflake) fits: calling a service, producing a
report, checking something and recording the result. There is no Python asset in the repo yet,
so this page is the pattern to follow, not a description of existing code. The shape below
constructs with the installed packages; the asset itself is an example.

## When Python, when not

| Task | Use |
|------|-----|
| Ingest from a REST API | dlt: a source folder with `pipelines.py` and `defs.yaml` |
| Transform data already in Snowflake | dbt model |
| Call an external service, run a Python library over query results, publish a summary | Python asset |

## Where the code goes

In the code location that owns the concern, as a module next to `definitions.py`. The two
existing locations build their assets from component trees (`dlt_pipelines/` and the
location's `defs/` package); a module outside those trees is not picked up automatically, which
is what you want: you merge it in explicitly.

```
src/orchestrator/locations/dbt/dbt_example/
├── __init__.py
├── definitions.py     # merges the component tree and your assets
├── assets.py          # new: the @asset functions
└── defs/dbt/defs.yaml # the DbtProjectComponent, untouched
```

A genuinely separate concern (own dependencies, own failure blast radius) is a new code location
instead; see the end of this page.

## Writing the asset

The example depends on the staged KNMI model and records its row count and latest observation
as asset metadata. Resources are typed function parameters; Dagster injects them by name from
the `resources` dict of the location's `Definitions`. Every signature gets full annotations.

```python title="src/orchestrator/locations/dbt/dbt_example/assets.py"
"""Python assets of the dbt_example location."""

from dagster import AssetExecutionContext, AssetKey, MaterializeResult, asset
from dagster_snowflake import SnowflakeResource

from orchestrator.resources.snowflake import SnowflakeSettings

# The staging layer schema: _STG, or <SNOWFLAKE_SCHEMA>_STG in dev. Reading settings never connects.
STG_SCHEMA = SnowflakeSettings.from_env().schema_for_layer("stg")


@asset(
    group_name="weather",
    kinds={"python", "snowflake"},
    deps=[AssetKey(["stg", "stg__knmi__climate_hourly"])],
)
def knmi_freshness_report(context: AssetExecutionContext, snowflake: SnowflakeResource) -> MaterializeResult:
    """Row count and latest observation of the staged KNMI data, as asset metadata."""
    with snowflake.get_connection() as conn:
        row_count, latest = conn.cursor().execute(
            f"SELECT COUNT(1), MAX(observed_at) FROM {STG_SCHEMA}.stg__knmi__climate_hourly"
        ).fetchone()
    context.log.info("stg__knmi__climate_hourly: %s rows, latest %s", row_count, latest)
    return MaterializeResult(metadata={"row_count": int(row_count), "latest_observed_at": str(latest)})
```

Points worth copying:

`deps=[AssetKey([...])]`
:   Upstream assets by key, not by import. dbt model keys are `<layer>/<name>`, so the staged
    model is `AssetKey(["stg", "stg__knmi__climate_hourly"])`; a dlt asset would be
    `AssetKey(["dlt", "ingest", "knmi", "climate_hourly"])`. Keys resolve across code
    locations, so a dependency on an asset in another location works the same way.

`schema_for_layer("stg")`
:   Never spell a layer schema by hand. `SnowflakeSettings.schema_for_layer()` returns `_STG` in
    the shared environments and `<SNOWFLAKE_SCHEMA>_STG` in dev, the same rule dbt and dlt use.
    The database is already the connection's default (`SNOWFLAKE_DATABASE`).

`snowflake: SnowflakeResource`
:   The parameter name is the resource key. The connection uses the same `.env` settings as
    everything else; `get_connection()` yields a `snowflake.connector` connection.

`MaterializeResult(metadata=...)`
:   Metadata shows up in the UI on every materialization. Return `None` when there is nothing
    to record.

`group_name` and `kinds`
:   The group is how the asset catalog is organized (dbt models use their package name, dlt
    loads `dlt_ingest_<source>`); `kinds` become the little tool icons.

## Merging it into the location

`definitions.py` currently returns `build_dbt_defs(...)` directly. Merge your assets and the
Snowflake resource into it with `Definitions.merge`, the same call `build_dbt_defs` and the dlt
location use for their jobs:

```python title="src/orchestrator/locations/dbt/dbt_example/definitions.py"
"""Dagster code location for the dbt_example project (see locations/dbt/shared.py)."""

from dagster import Definitions

from orchestrator.locations.dbt.dbt_example import defs as _defs_module
from orchestrator.locations.dbt.dbt_example.assets import knmi_freshness_report
from orchestrator.locations.dbt.shared import build_dbt_defs
from orchestrator.resources.snowflake import SnowflakeSettings

defs = Definitions.merge(
    build_dbt_defs("dbt_example", _defs_module),
    Definitions(
        assets=[knmi_freshness_report],
        resources={"snowflake": SnowflakeSettings.from_env().dagster_resource()},
    ),
)
```

`SnowflakeSettings.from_env().dagster_resource()` builds a `dagster_snowflake.SnowflakeResource`
from the `SNOWFLAKE_*` variables. Building it does not connect, so the location still loads
without a `.env` (CI and `just validate` rely on that); the connection opens when the asset
runs. One resource dict per location is enough; do not construct settings inside asset bodies.

Because `job_dbt_example_build_all` selects `AssetSelection.all()`, the new asset joins that
job as well.

## Validate and run

```bash
just fmt
just typecheck
just validate                                                      # the location loads with the asset
just dagster asset list -m orchestrator.locations.dbt.dbt_example.definitions
just start                                                         # materialize it from the UI
```

Unit tests stay offline: put the logic that is worth testing (parsing, calculations) in plain
functions and test those under `tests/`; leave the Snowflake round trip to a manual
materialization. See [Testing](testing.md).

## A new code location

If the asset is its own concern, give it its own location rather than growing `dbt_example`:

1. Create `src/orchestrator/locations/<name>/` with `__init__.py`, `assets.py` and a
   `definitions.py` that exposes a top-level `defs`:

    ```python title="src/orchestrator/locations/<name>/definitions.py"
    """Dagster code location <name>."""

    from dagster import Definitions

    from orchestrator.locations.<name>.assets import my_asset
    from orchestrator.resources.snowflake import SnowflakeSettings

    defs = Definitions(
        assets=[my_asset],
        resources={"snowflake": SnowflakeSettings.from_env().dagster_resource()},
    )
    ```

2. Add it to `workspace.yaml`:

    ```yaml title="workspace.yaml (excerpt)"
      - python_module:
          module_name: orchestrator.locations.<name>.definitions
          location_name: "<name>"
    ```

3. `just validate`, then `just start`.

Locations never import each other. Anything the new location needs from `dlt` or a dbt
location it names by asset key in `deps`; shared code lives under `orchestrator.resources` or
`orchestrator.utils`, never inside another location's package. Details on
[Orchestration](../architecture/orchestration.md).
