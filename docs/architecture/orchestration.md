---
icon: material/factory
---

# Orchestration (Dagster)

Dagster is the control plane. Every dlt resource and every dbt model, seed and test is an
asset, organized in code locations that load independently. `just start` runs
`dagster dev -w workspace.yaml` on <http://localhost:3000>; the UI shows one asset graph across
all locations. Dagster reads the same `.env` as everything else, so it runs in whichever
environment the checkout is configured for: your personal schemas in `dev`, the `_<LAYER>`
schemas elsewhere.

## workspace.yaml

`workspace.yaml` at the repository root is the authoritative list of code locations. Each entry
names a Python module of the `orchestrator` package that exposes a top-level `defs`:

```yaml title="workspace.yaml"
load_from:
  - python_module:
      module_name: orchestrator.locations.dlt.definitions
      location_name: "dlt"

  - python_module:
      module_name: orchestrator.locations.dbt.dbt_example.definitions
      location_name: "dbt_example"
```

| Location | Module | Owns |
|----------|--------|------|
| `dlt` | `orchestrator.locations.dlt.definitions` | Every dlt load under `dlt_pipelines/pipelines/ingest/`, plus `job_dlt_ingest_all` |
| `dbt_example` | `orchestrator.locations.dbt.dbt_example.definitions` | The `dbt_example` project as assets, including the `dbt_common` models it builds, plus `job_dbt_example_build_all` |

One location per concern: the ingestion package, and one per dbt project, which is one per
Project of the mesh. The file ends with a commented block for the next dbt project. A genuinely
separate Python concern is one more entry as well.

## Locations load in subprocesses and never import each other

`dagster dev` starts every location in its own subprocess. That gives parallel startup, a
per-location *Reload* button in the UI, and fault isolation: a broken dbt project does not take
the dlt assets down. The flip side is a rule: location modules never import one another.
Nothing in `orchestrator.locations.dlt` knows about `orchestrator.locations.dbt`, and vice
versa. Shared code lives outside the location packages (`orchestrator.resources`,
`orchestrator.locations.dbt.shared`).

```mermaid
flowchart TD
    WS["workspace.yaml"] --> DLT["dlt<br/>subprocess"]
    WS --> DBT["dbt_example<br/>subprocess"]
    DLT -- "asset key<br/>dlt/ingest/knmi/climate_hourly" --> DBT
```

## Component trees

Neither location writes assets by hand. Both call `ComponentTree.from_module(...)`, which walks a
Python package, finds every `defs.yaml`, and builds the definitions those components declare.

### The dlt location

```python title="src/orchestrator/locations/dlt/definitions.py"
def _build_defs() -> Definitions:
    loaded = ComponentTree.from_module(defs_module=_dlt_pipelines, project_root=_PROJECT_ROOT).build_defs()
    job_all = define_asset_job(
        name="job_dlt_ingest_all",
        selection=AssetSelection.key_prefixes(["dlt", "ingest"]),
        description="Run every dlt ingest pipeline.",
        op_retry_policy=RetryPolicy(max_retries=2, delay=30, backoff=Backoff.EXPONENTIAL),
    )
    schedule_daily = ScheduleDefinition(
        name="schedule_dlt_ingest_daily",
        job=job_all,
        cron_schedule=_INGEST_CRON,
        default_status=DefaultScheduleStatus.STOPPED,
        description="Daily run of job_dlt_ingest_all.",
    )
    return Definitions.merge(loaded, Definitions(jobs=[job_all], schedules=[schedule_daily]))


defs = _build_defs()
```

The module it walks is the whole `dlt_pipelines` package, so
`dlt_pipelines/pipelines/ingest/knmi/defs.yaml` (a `dagster_dlt.DltLoadCollectionComponent`)
is found without registration. Adding a source is adding a folder with a `defs.yaml`. Its
assets join `job_dlt_ingest_all` automatically because the job selects by key prefix. See
[Ingestion](ingestion.md#the-dagster-component).

### The dbt locations

Every dbt location is two small files. `definitions.py` calls the shared factory with the
project name and its `defs` package:

```python title="src/orchestrator/locations/dbt/dbt_example/definitions.py"
from orchestrator.locations.dbt.dbt_example import defs as _defs_module
from orchestrator.locations.dbt.shared import build_dbt_defs

defs = build_dbt_defs("dbt_example", _defs_module)
```

`build_dbt_defs()` in `src/orchestrator/locations/dbt/shared.py` loads the component tree under
`defs/` and adds `job_<project>_build_all`, selecting the keys that tree produced. The project name
it takes only names the job; if it matches no asset key prefix, the factory raises, because
`definitions.py` and `defs/dbt/defs.yaml` then point at different dbt projects. The tree contains
one component:

```yaml title="src/orchestrator/locations/dbt/dbt_example/defs/dbt/defs.yaml"
type: orchestrator.locations.dbt.shared.DataMeshDbtProjectComponent

attributes:
  project:
    project_dir: '{{ context.project_root }}/dbt/dbt_example'
    profiles_dir: '{{ context.project_root }}/dbt'
    prepare_project_cli_args: ["parse", "--quiet"]
  select: "fqn:*"
```

`prepare_project_cli_args` makes the location run `dbt parse --quiet` on every load, so the
manifest always matches the SQL on disk. That is also why `dbt deps` must have run first:
without `packages/` the parse fails and the location shows an error. `just dbt-all deps` fixes
it.

## Asset keys

| Kind | Key | Example | Group |
|------|-----|---------|-------|
| dlt resource | `dlt/ingest/<source>/<entity>` (from `defs.yaml`: `key_prefix` + lowercased resource name) | `dlt/ingest/knmi/climate_hourly` | `dlt/ingest/<source>` |
| dbt model, seed | `<project>/<path in the project>/<node name>`; nodes from a package get `<project>/packages/<package>/...` | `dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly`, `dbt_example/packages/dbt_common/seeds/seed_month`, `dbt_example/packages/dbt_common/models/04_mrt/common/dim__common__calendar` | the key without its last segment: `dbt_example/models/02_stg/knmi` |
| dbt source | `config.meta.dagster.asset_key` from the source YAML | `dlt/ingest/knmi/climate_hourly` | the upstream asset's group |

The dbt keys come from `DataMeshDbtTranslator` in `src/orchestrator/locations/dbt/shared.py`:
the project name, the node's path inside the project (`models/02_stg/knmi`), then its name; a
node from an installed package gets `packages/<package>` after the project name. Nothing in
the key depends on the physical schema, so it is the same in every environment: `DBT_USERNAME_STG`
in `dev` and `_STG` in `prd` both show up under `dbt_example/models/02_stg/...`. The group is
the key without its last segment, so the UI nests assets by project, package, layer and domain.
Search the asset catalog for the model name; when you need the full key in code, it is
`AssetKey(["dbt_example", "models", "02_stg", "knmi", "stg__knmi__climate_hourly"])`.

## Lineage across code locations

The dlt asset and the dbt staging model live in different locations and different processes,
yet the graph shows `dlt/ingest/knmi/climate_hourly` feeding
`dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly`.
No import makes that happen; the key does. The dbt source declares it:

```yaml title="dbt/dbt_example/sources/src_knmi.yml (excerpt)"
sources:
  - name: knmi
    schema: "{{ ((target.schema | trim | upper) or 'DBT') ~ '_SRC' if target.name | trim | lower in ['dev', 'dummy'] else '_SRC' }}"
    tables:
      - name: climate_hourly
        identifier: knmi__climate_hourly
        config:
          meta:
            dagster:
              asset_key: ["dlt", "ingest", "knmi", "climate_hourly"]
```

Dagster resolves both locations' definitions into one global graph and joins on equal keys.
The same mechanism works in the other direction: a Python asset or a second dbt project that
depends on `dim__common__calendar` names
`AssetKey(["dbt_example", "packages", "dbt_common", "models", "04_mrt", "common", "dim__common__calendar"])`
and gets the edge. Two locations declaring the *same materializable* key is an error; the
project prefix keeps dbt keys apart, so the reason only one dbt project builds the `dbt_common`
models is the tables, which would otherwise be built twice in the same database.

## Jobs

Two convenience jobs exist for the Launchpad; the rest is asset selection in the UI.

| Job | Location | Selection |
|-----|----------|-----------|
| `job_dlt_ingest_all` | `dlt` | Every asset with key prefix `dlt/ingest` |
| `job_dbt_example_build_all` | `dbt_example` | The dbt component's own assets, which runs `dbt build` for the whole project |

A second dbt project gets `job_<project>_build_all` from the same factory. The dbt job selects the
keys the component produced, not `AssetSelection.all()`, so a Python asset merged into the same
location keeps its own place in the graph instead of joining the dbt build unannounced.

## Automation: one schedule, one condition, one retry policy

Nothing fires on its own after `just start`. Both automation definitions ship **stopped**, so the
starter shows the pattern without ever launching a run you did not ask for. Turn them on under
*Automation* in the UI; the instance remembers the switch in `.dagster/`.

| Definition | Location | What it does | Ships |
|---|---|---|---|
| `schedule_dlt_ingest_daily` | `dlt` | `job_dlt_ingest_all` on `_INGEST_CRON` (`0 5 * * *`, UTC) | `DefaultScheduleStatus.STOPPED` |
| `default_automation_condition_sensor` | every dbt location | Runs the `AutomationCondition.eager()` every dbt asset carries: a model rebuilds once the asset feeding its source has been loaded | `DefaultSensorStatus.STOPPED` (Dagster's default) |

That pair is the whole chain: the schedule ingests, the condition pulls the dbt models through
behind it. No schedule per layer, and no cron to keep in step with the model graph.

- **The cron** lives in `_INGEST_CRON` in `src/orchestrator/locations/dlt/definitions.py`. One cron
  covers every source; a source that needs its own cadence gets its own `ScheduleDefinition` on a
  narrower `AssetSelection`. Add `execution_timezone="Europe/Amsterdam"` for a local wall clock.
- **The condition** is set once, in `DataMeshDbtTranslator.get_asset_spec()`
  (`src/orchestrator/locations/dbt/shared.py`), so every model of every dbt project has it.
- **Retries**: `job_dlt_ingest_all` carries
  `op_retry_policy=RetryPolicy(max_retries=2, delay=30, backoff=Backoff.EXPONENTIAL)`. A source API
  that rate-limits or times out is the usual failure, and every pipeline merges on a primary key, so
  re-running an overlapping window is safe. It applies to runs of the job (the schedule's runs
  included); materializing an asset ad hoc from the graph does not go through the job, so it does not
  retry. dbt failures are handled the other way around, with *Re-execute, from failure*.

In a deployed environment, flip `default_status` to `RUNNING` so the schedule arrives switched on,
and pass `AutomationConditionSensorDefinition(..., default_status=DefaultSensorStatus.RUNNING)` if
you want the same for the condition.

## The local instance

`DAGSTER_HOME` is `.dagster/` inside the repository (exported by the justfile and `.envrc`).
Run history and event logs land there, git-ignored; the one versioned file is the instance
config:

```yaml title=".dagster/dagster.yaml"
telemetry:
  enabled: false

run_coordinator:
  module: dagster.core.run_coordinator
  class: DefaultRunCoordinator

run_launcher:
  module: dagster.core.launcher
  class: DefaultRunLauncher
```

Runs start immediately in a subprocess (no daemon queue), with no limit on concurrent runs; a
limit needs the `QueuedRunCoordinator` and the daemon. Deleting
`.dagster/` (keep `dagster.yaml`) resets your run history and nothing else.

!!! warning "An edited `.env` needs a restart"
    `.env` is read once, at startup, by `just` (`set dotenv-load`) and by the Dagster CLI itself;
    code servers and run subprocesses inherit that one copy. Nothing re-reads the file afterwards,
    so editing `.env` while the UI is up changes nothing, not even after *Reload* on a code
    location: run `just stop && just start`. A `secrets:` block in `dagster.yaml` does not help,
    because `DefaultRunLauncher` starts runs inside the code server, which skips the secrets loader.

`pyproject.toml` also carries a `[tool.dg]` block for Dagster's `dg` CLI. Its `defs_module`
points at the empty `orchestrator.defs` package so the component cache has one home; the real
locations are the ones in `workspace.yaml`.

## Working with it

```bash
just start                                                         # UI on :3000, Ctrl+C stops
just stop                                                          # stop dagster dev on port 3000; another program there is reported, not killed
just validate                                                      # load every location, no UI
just dagster asset list -m orchestrator.locations.dlt.definitions  # any Dagster CLI command
```

`just validate` is the check to run after touching `src/`, `dlt_pipelines/`, `dbt/` or
`workspace.yaml`: it loads every location exactly like `just start` does and fails on import
errors, broken `defs.yaml` files and dbt parse errors. CI runs the same command with
`DBT_TARGET=dummy`.

## Related pages

- [Ingestion](ingestion.md) and [Transformation](transformation.md): what the two locations load
- [Adding Python assets](../development/adding-python-assets.md): merging a plain `@asset` into a location
- [Adding a project](../development/adding-projects.md): the third code location
