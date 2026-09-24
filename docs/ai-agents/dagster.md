---
icon: material/factory
---

# Dagster

Agent guide for the Dagster layer: where definitions live, the loading pattern to follow, how the two components turn dlt and dbt into assets, and what to validate after a change. The architecture reference is [Orchestration](../architecture/orchestration.md); this page keeps the operational knowledge you need while editing `src/orchestrator/`. Ground rules for all agent work are in `AGENTS.md`.

## Orientation

- `workspace.yaml` at the repo root is the authoritative list of code locations. Each entry maps a `location_name` to a Python module exposing a top-level `defs`. Read a location's `definitions.py` docstring first: it states what that location owns.
- One code location per concern: the dlt ingestion package, and one per dbt project (one project per mesh node). Locations load in their own subprocess and never import each other. Cross-location lineage resolves through shared asset keys: dbt sources declare `config.meta.dagster.asset_key` in `sources/src_<source>.yml`, matching the dlt asset key `dlt/ingest/<source>/<entity>`.
- The same code runs in every environment. `ENVIRONMENT` in `.env` (default `dev`) decides where things land: personal schemas `<SNOWFLAKE_SCHEMA>_<LAYER>` in `dev`, the `_<LAYER>` schemas elsewhere. Asset keys do not change between environments.

| Location | Module | Owns |
|---|---|---|
| `dlt` | `orchestrator.locations.dlt.definitions` | Every dlt load under `dlt_pipelines/pipelines/ingest/`, one asset per dlt resource, plus `job_dlt_ingest_all` |
| `dbt_example` | `orchestrator.locations.dbt.dbt_example.definitions` | The `dbt_example` project, including the `dbt_common` models it builds, plus `job_dbt_example_build_all` |

A second dbt project is one more block in `workspace.yaml` (there is a commented template at the bottom of the file) and one more folder under `src/orchestrator/locations/dbt/`; see [adding a project](../development/adding-projects.md).

## How definitions are built

Both locations build their `Definitions` inside a function and assign the result to a module-level `defs`:

- `src/orchestrator/locations/dlt/definitions.py` has a private `_build_defs()`.
- `src/orchestrator/locations/dbt/shared.py` has `build_dbt_defs(project_name, defs_module)`, called by every dbt location's `definitions.py` with its project name and its `defs` package. `src/orchestrator/locations/dbt/dbt_example/definitions.py` does nothing else: import the `defs` package, import the factory, call `build_dbt_defs("dbt_example", _defs_module)`.

Both do the same two things: load the component tree with `ComponentTree.from_module(defs_module=..., project_root=...)` and `Definitions.merge` the result with one `define_asset_job` for the Launchpad.

!!! danger "Do not switch to `load_from_defs_folder`"
    `[tool.dg.project].defs_module` in `pyproject.toml` points at `orchestrator.defs`, an intentionally empty package (it exists so the dg CLI has a defs folder and the component cache lands in one `.local_defs_state/`). `load_from_defs_folder` would load that empty tree. Always use `ComponentTree.from_module` in a location's `definitions.py`, matching the existing locations.

## The two components

Everything that is an asset today comes from a component `defs.yaml`; there is no hand-written `@asset` yet.

=== "dlt"

    `dlt_pipelines/pipelines/ingest/knmi/defs.yaml`, type `dagster_dlt.DltLoadCollectionComponent`, in full:

    ```yaml
    type: dagster_dlt.DltLoadCollectionComponent

    attributes:
      loads:
        - pipeline: .pipelines.pipeline
          source: .pipelines.source
          translation:
            key: '{{ resource.name | lower }}'
            key_prefix: '{{ ["dlt", "ingest", "knmi"] }}'
            group_name: dlt/ingest/knmi
            kinds:
              - dlt
              - snowflake
            # The API is the start of the graph: no placeholder upstream asset per resource.
            deps: []
    ```

    Each load points at the module-level `pipeline` and `source` objects in the sibling `pipelines.py`. The translation sets the asset key to the resource name under the prefix, the group and the kinds; `deps: []` stops dagster-dlt from adding a placeholder upstream asset per resource. Result: `dlt/ingest/knmi/climate_hourly`, and the table `knmi__climate_hourly` in the source layer.

=== "dbt"

    `src/orchestrator/locations/dbt/dbt_example/defs/dbt/defs.yaml`, type `orchestrator.locations.dbt.shared.DataMeshDbtProjectComponent` (dagster-dbt's `DbtProjectComponent` with the key scheme below). It points at `dbt/dbt_example` with the shared `dbt/` profiles dir, selects `*`, and re-parses the project on every code-location load (`prepare_project_cli_args: ["parse", "--quiet"]`), so the manifest always matches the models on disk. Asset keys follow the file path, `<project>/models/<layer>/<domain>/<name>` (`dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly`), with `<project>/packages/<package>/...` for nodes from a package, the same in every environment. Sources take their key from `config.meta.dagster.asset_key`, and the group is the key without its last segment (`dbt_example/models/02_stg/knmi`), which is what nests the assets in the UI (`DataMeshDbtTranslator` in `shared.py`).

!!! warning "Component-relative references"
    The `.pipelines.pipeline` style references in a `defs.yaml` resolve relative to the folder that holds the `defs.yaml`. Keep `pipelines.py` next to it.

## Jobs, schedules, sensors

| Definition | Location | Selection |
|---|---|---|
| `job_dlt_ingest_all` | `dlt` | `AssetSelection.key_prefixes(["dlt", "ingest"])`: every dlt ingest asset |
| `job_dbt_example_build_all` | `dbt_example` | `AssetSelection.all()`: `dbt build` for the whole project |

There are no schedules or sensors yet. Job names carry the `job_` prefix; the naming page covers Dagster definition names: [Naming](../conventions/naming.md).

## Entry points and local state

| Command | What it runs |
|---|---|
| `just start` | `uv run dagster dev -w workspace.yaml -h 127.0.0.1 -p 3000`, the UI on port 3000, foreground |
| `just stop` | Kills whatever listens on port 3000 |
| `just dagster <args>` | The Dagster CLI, e.g. `just dagster asset list -m orchestrator.locations.dlt.definitions` |
| `just validate` | `uv run dagster definitions validate -w workspace.yaml`: loads every location like `start` does, without the UI |

`DAGSTER_HOME` is `.dagster/` inside the repo (set by the `justfile` and `.envrc`). `.dagster/dagster.yaml` is versioned: telemetry off, `DefaultRunCoordinator` and `DefaultRunLauncher` (runs start immediately in a subprocess, no daemon queue), `max_concurrent_runs: 4`. Everything else in `.dagster/` is run history and safe to delete. The component cache lands in `.local_defs_state/`, also git-ignored.

CI runs `just validate`'s command with `DBT_TARGET=dummy`, because the `dbt_example` location parses the dbt project on load and CI has no `.env`. Do the same locally if your `.env` is not filled in yet.

## Resources

There is no central resource registry. `SnowflakeSettings.from_env()` in `src/orchestrator/resources/snowflake.py` is the one reader of the `SNOWFLAKE_*` variables and `ENVIRONMENT`, and it hands out what each consumer needs:

- `dlt_credentials()` for the dlt destination (`dlt_pipelines/utils/destination.py`)
- `schema_for_layer("src")` for the dlt dataset: `_SRC`, or `<SNOWFLAKE_SCHEMA>_SRC` in `dev`
- `connect()` for Python assets that query Snowflake directly (open it inside the asset body)
- `connect()` for a plain connector connection (used by `scripts/snowflake.py`)

Where new asset code goes and how to wire a resource into it: [Adding Python assets](../development/adding-python-assets.md). The settings object itself: [Snowflake](snowflake.md).

## Retrying failed runs

Dagster's built-in **Re-execute, from failure** on a finished run is the retry path; there is no separate retry job.

- **`job_dbt_example_build_all`** is an asset job, so re-execute-from-failure re-runs only the failed and never-attempted assets. The dbt integration translates that asset subset into a `dbt build --select` of just those models, the asset-aware equivalent of `dbt retry`. Failed dbt tests show up as failed asset checks on a succeeded model and are re-run the same way.
- **`job_dlt_ingest_all`**: one asset per dlt resource, so a retry re-runs only the resources that failed. Each pipeline uses `merge` with a primary key, so re-running an overlapping window is safe.
- Assets skipped because of an upstream failure count as "not yet materialized" and are included in the retry.

## After making changes

Run at least steps 1 to 4 before presenting changes.

### 1. Format and lint

```bash
just fmt
```

Runs `ruff format .`, `ruff check --fix .` and `sqlfluff fix models` in the active dbt project. `just lint` is the read-only variant CI uses.

### 2. Type check

```bash
just typecheck
```

`ty check` over `src/`, `dlt_pipelines/`, `scripts/` and `tests/` (`[tool.ty.src]` in `pyproject.toml`).

### 3. Validate definitions

```bash
just validate
```

Loads each code location in its own subprocess and parses every `defs.yaml`. Catches import errors, broken component references, and a dbt project that does not parse. If this fails, nothing will work.

### 4. Run tests

```bash
just test
```

### 5. Check the dbt side (if you touched sources, models or the component)

```bash
just dbt-all deps
just dbt parse
```

Without `deps`, `parse` fails on missing packages, and so does the code location.

### 6. Full validation

```bash
just pre-commit
```

Runs every hook on every file (ruff, ty, dbt parse, sqlfluff, Dagster validation, Terraform YAML).

## Key source files

| What | Where |
|---|---|
| Workspace (authoritative location list) | `workspace.yaml` |
| dlt code location | `src/orchestrator/locations/dlt/definitions.py` |
| dbt location factory | `src/orchestrator/locations/dbt/shared.py` |
| dbt_example location and component | `src/orchestrator/locations/dbt/dbt_example/definitions.py`, `defs/dbt/defs.yaml` |
| dlt component | `dlt_pipelines/pipelines/ingest/knmi/defs.yaml` |
| Snowflake settings | `src/orchestrator/resources/snowflake.py` |
| Instance config | `.dagster/dagster.yaml` |

Upstream documentation: <https://docs.dagster.io>.

## Related pages

- [Orchestration](../architecture/orchestration.md): code locations, components, jobs
- [Adding Python assets](../development/adding-python-assets.md): the how-to for new assets and code locations
- [Adding a project](../development/adding-projects.md): one more code location per project
- [Naming](../conventions/naming.md): definition and asset-key names
- [Commands reference](../reference/commands.md): every `just` recipe
