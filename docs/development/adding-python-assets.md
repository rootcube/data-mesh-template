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
as asset metadata. It opens its own connection with `SnowflakeSettings.from_env().connect()`;
the repo has no Dagster resources yet, and one connection per asset is simpler than a resource
dict until several assets share one. Every signature gets full annotations.

```python title="src/orchestrator/locations/dbt/dbt_example/assets.py"
"""Python assets of the dbt_example location."""

from dagster import AssetExecutionContext, AssetKey, MaterializeResult, asset

from orchestrator.resources.snowflake import SnowflakeSettings

# The staging layer schema: _STG, or <SNOWFLAKE_SCHEMA>_STG in dev. Reading settings never connects.
STG_SCHEMA = SnowflakeSettings.from_env().schema_for_layer("stg")


@asset(
    group_name="weather",
    kinds={"python", "snowflake"},
    deps=[AssetKey(["dbt_example", "models", "02_stg", "knmi", "stg__knmi__climate_hourly"])],
)
def knmi_freshness_report(context: AssetExecutionContext) -> MaterializeResult:
    """Row count and latest observation of the staged KNMI data, as asset metadata."""
    with SnowflakeSettings.from_env().connect() as conn:
        row_count, latest = conn.cursor().execute(
            f"SELECT COUNT(1), MAX(observed_at) FROM {STG_SCHEMA}.stg__knmi__climate_hourly"
        ).fetchone()
    context.log.info("stg__knmi__climate_hourly: %s rows, latest %s", row_count, latest)
    return MaterializeResult(metadata={"row_count": int(row_count), "latest_observed_at": str(latest)})
```

Points worth copying:

`deps=[AssetKey([...])]`
:   Upstream assets by key, not by import. dbt model keys follow the file path, so the staged
    model is `AssetKey(["dbt_example", "models", "02_stg", "knmi", "stg__knmi__climate_hourly"])`;
    a dlt asset would be
    `AssetKey(["dlt", "ingest", "knmi", "climate_hourly"])`. Keys resolve across code
    locations, so a dependency on an asset in another location works the same way.

`schema_for_layer("stg")`
:   Never spell a layer schema by hand. `SnowflakeSettings.schema_for_layer()` returns `_STG` in
    the shared environments and `<SNOWFLAKE_SCHEMA>_STG` in dev, the same rule dbt and dlt use.
    The database is already the connection's default (`SNOWFLAKE_DATABASE`).

`SnowflakeSettings.from_env().connect()`
:   The same `.env` settings as dbt and dlt, opened inside the asset body so the location still
    loads without a `.env`. `connect()` returns a `snowflake.connector` connection; use it as a
    context manager so it closes.

`MaterializeResult(metadata=...)`
:   Metadata shows up in the UI on every materialization. Return `None` when there is nothing
    to record.

`group_name` and `kinds`
:   The group is how the asset catalog is organized (dbt models use their key without its last
    segment, such as `dbt_example/models/02_stg/knmi`; dlt loads `dlt/ingest/<source>`); `kinds`
    become the little tool icons.

## Merging it into the location

`definitions.py` currently returns `build_dbt_defs(...)` directly. Merge your assets into it
with `Definitions.merge`, the same call `build_dbt_defs` and the dlt location use for their jobs:

```python title="src/orchestrator/locations/dbt/dbt_example/definitions.py"
"""Dagster code location for the dbt_example project (see locations/dbt/shared.py)."""

from dagster import Definitions

from orchestrator.locations.dbt.dbt_example import defs as _defs_module
from orchestrator.locations.dbt.dbt_example.assets import knmi_freshness_report
from orchestrator.locations.dbt.shared import build_dbt_defs

defs = Definitions.merge(
    build_dbt_defs("dbt_example", _defs_module),
    Definitions(assets=[knmi_freshness_report]),
)
```

Nothing connects at import time, so the location still loads without a `.env` (CI and
`just validate` rely on that); the connection opens when the asset runs. Once several assets
share a connection, promote it to a `dagster_snowflake.SnowflakeResource` in the location's
`resources` dict; until then the inline `connect()` is the pattern.

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

    defs = Definitions(assets=[my_asset])
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
