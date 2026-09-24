---
icon: material/pipe
---

# dlt

Working guide for changes to the ingestion layer: the `dlt_pipelines/` package, the source layer it loads into, the Snowflake destination, the standalone runner, and the `dlt` Dagster code location. This page covers what you need while editing and the validation to run afterwards. The concepts live on the canonical pages:

- [Ingestion](../architecture/ingestion.md): how a source lands in the `_SRC` layer, write dispositions, where state lives
- [Adding a dlt load](../development/adding-dlt-loads.md): the step-by-step how-to for a new source, including the dbt side

## Orientation

One top-level package, `dlt_pipelines/`, backs the single `dlt` code location. One folder per source under `pipelines/ingest/`; everything else is shared.

| Path | What it is |
|---|---|
| `dlt_pipelines/pipelines/ingest/<source>/constants.py` | URLs, station lists, window sizes: the knobs |
| `dlt_pipelines/pipelines/ingest/<source>/source.py` | The fetch logic: plain functions that yield dicts |
| `dlt_pipelines/pipelines/ingest/<source>/pipelines.py` | The `@dlt.source`, its resources, and the module-level `source` and `pipeline` objects |
| `dlt_pipelines/pipelines/ingest/<source>/defs.yaml` | `dagster_dlt.DltLoadCollectionComponent`: turns `source` and `pipeline` into Dagster assets |
| `dlt_pipelines/utils/destination.py` | `snowflake_destination()`, `load_stage()` and `source_dataset()`: the one Snowflake destination, the internal stage its load files go through and the source-layer schema every pipeline loads into |
| `dlt_pipelines/__main__.py` | The standalone runner behind `just dlt list` / `just dlt run <source>` |
| `src/orchestrator/locations/dlt/definitions.py` | The code location: loads the component tree and adds `job_dlt_ingest_all` |
| `.dlt/config.toml` | Runtime tuning (see below) |

The only source today is `knmi`: hourly weather observations from the public KNMI `uurgegevens` endpoint, no authentication, seven stations, the last 30 days and never anything before `START_DATE` (2026-01-01), fetched in 10-day chunks (`constants.py`).

## Where the data lands

Every source lands in the **source layer** of the project database as one table per entity, named `<source>__<entity>`:

| Environment | Schema | Example table |
|---|---|---|
| `dev` | `<SNOWFLAKE_SCHEMA>_SRC`, your personal source schema, created on first load | `DB_EXAMPLE_DEV.DBT_USERNAME_SRC.KNMI__CLIMATE_HOURLY` |
| `tst`, `acc`, `prd` | `_SRC`, provisioned by Terraform | `DB_EXAMPLE_PRD._SRC.KNMI__CLIMATE_HOURLY` |

`source_dataset()` in `dlt_pipelines/utils/destination.py` is `SnowflakeSettings.from_env().schema_for_layer("src")`, so dlt follows exactly the rule dbt uses (`dbt_common.generate_schema_name`) and the source YAML repeats with `env_var`. The role that owns this layer in deployed environments is `RL_<PROJECT>_<ENV>__ING` ("used by ingestion tooling to load data into the SRC layer" in `terraform/config/roles/ingest.yaml`); in `dev` your engineer role inherits it.

## The pipeline pattern

Every source follows `dlt_pipelines/pipelines/ingest/knmi/pipelines.py`, shown here in full because it is the template:

```python
"""dlt pipeline: KNMI hourly weather observations -> Snowflake source layer (knmi__climate_hourly).

Every source lands in the project's source layer (`_SRC`, or your personal `<PREFIX>_SRC` in dev)
as `<source>__<entity>`. `merge` with a primary key keeps the table free of duplicates when the
pipeline runs daily over an overlapping window; `just dlt run knmi --full-refresh` reloads it.
"""

from collections.abc import Iterator

import dlt

from dlt_pipelines.pipelines.ingest.knmi.source import fetch_hourly_observations
from dlt_pipelines.utils.destination import snowflake_destination, source_dataset

SOURCE = "knmi"
ENTITY = "climate_hourly"


@dlt.source(name=f"{SOURCE}__{ENTITY}", max_table_nesting=0)
def knmi_source() -> Iterator[dlt.sources.DltResource]:
    """KNMI hourly observations for a handful of stations, last 30 days."""

    @dlt.resource(
        name=ENTITY,
        table_name=f"{SOURCE}__{ENTITY}",
        write_disposition="merge",
        primary_key=["station_code", "date", "hour"],
    )
    def climate_hourly() -> Iterator[dict]:
        yield from fetch_hourly_observations()

    yield climate_hourly()


source = knmi_source()

pipeline = dlt.pipeline(
    pipeline_name=f"ingest_{SOURCE}",
    destination=snowflake_destination(),
    dataset_name=source_dataset(),
)
```

What matters in it:

- **Module-level `source` and `pipeline`.** Both the Dagster component and the standalone runner import exactly these two names. Rename them and both break.
- **`name=ENTITY` and `table_name=f"{SOURCE}__{ENTITY}"`.** The resource name becomes the Dagster asset key (`dlt/ingest/knmi/climate_hourly`); the table name puts the source prefix on the Snowflake table (`knmi__climate_hourly`), because every source shares the one `_SRC` schema.
- **`dataset_name=source_dataset()`.** The source-layer schema for the current environment; dlt creates it on first load in `dev`. dbt reads it through `sources/src_<source>.yml`.
- **`merge` with a primary key.** Running daily over an overlapping window stays free of duplicates. `just dlt run knmi --full-refresh` drops the source's tables and state first (`refresh="drop_sources"`).
- **`max_table_nesting=0`.** Nested JSON stays in one table instead of fanning out into child tables.
- **Fetching lives in `source.py`.** `fetch_hourly_observations()` uses `dlt.sources.helpers.requests` and yields plain dicts; dlt infers the schema and lowercases the KNMI field names. Mirror the API here; renames, casts and unit conversions belong in the dbt staging model.

The matching `defs.yaml`, in full:

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

Copy it and change the source name in two places (`key_prefix` and `group_name`). `deps: []` keeps the API at the start of the asset graph instead of a placeholder upstream asset per resource.

!!! warning "Python files must sit next to their `defs.yaml`"
    The `.pipelines.pipeline` references resolve relative to the folder holding the `defs.yaml`. Moving `pipelines.py` elsewhere breaks the component even when the import path looks plausible.

## The destination

`dlt_pipelines/utils/destination.py` builds `dlt.destinations.snowflake(...)` from `SnowflakeSettings.from_env().dlt_credentials()`: the same `SNOWFLAKE_*` variables dbt and Dagster use, key-pair authentication only. Credentials are validated when a pipeline *runs*, not when the module is imported, so `just validate` and the Dagster code location work without a `.env`.

Load files go through a named internal stage, not the implicit table stage: `stage_name=load_stage(settings)` is `DB_<PROJECT>_<ENV>._SRC.ST_DLT`, created by Terraform in the provisioned source layer (`terraform/stages.tf`) and the same in every environment, `dev` included. dlt `PUT`s the JSONL files there under a folder per load id and runs `COPY INTO` from it; the ingest role has `READ` and `WRITE` on the stage, engineers inherit that in `dev`. Files stay after the load (dlt's `keep_staged_files` default); `just sf query "LIST @_SRC.ST_DLT"` shows them.

## Running a pipeline

=== "Standalone"

    ```bash
    just dlt list                     # every package under pipelines/ingest/ with a pipelines module
    just dlt run knmi                 # pipeline.run(source), prints the load info
    just dlt run knmi --full-refresh  # drop the source's tables and state first
    ```

    That is `uv run python -m dlt_pipelines ...`. Discovery is by folder: any package under `dlt_pipelines/pipelines/ingest/` shows up in `list` (`tests/test_dlt_pipelines.py` checks exactly that for `knmi`).

=== "Through Dagster"

    `just start`, then materialize `dlt/ingest/knmi/climate_hourly` in the UI, or launch `job_dlt_ingest_all`. Same `source` and `pipeline` objects, so the two paths cannot drift.

Check the result either way with `just sf query "SELECT COUNT(1) FROM dbt_username_src.knmi__climate_hourly"`, with your own `SNOWFLAKE_SCHEMA` prefix instead of `dbt_username` (`just sf check` prints the layer schemas it resolved).

## Runtime configuration

`.dlt/config.toml`, found through `DLT_PROJECT_DIR` (the repo root, set by the `justfile` and `.envrc`):

- Telemetry off, log level `WARNING`. `RUNTIME__LOG_LEVEL` in `.env` overrides it for local runs (`INFO` shows each step, `DEBUG` everything).
- Worker counts: `extract` 4, `normalize` 2, `load` 2. Laptop-sized on purpose.
- No credentials in the file, ever. The destination reads `SNOWFLAKE_*` from the environment.

`DLT_DATA_DIR` is `.dlt/data/` inside the repo: the working directory for extracted and normalized files. Local state lives inside the repo on purpose, so deleting `.dagster/` and `.dlt/data/` resets everything (the `justfile` says so); `just init` recreates both folders.

## After making changes

Run at least steps 1 to 4 before presenting work.

### 1. Format, lint, type-check

```bash
just fmt
just typecheck
```

`just fmt` runs `ruff format .` and `ruff check --fix .` over the whole repo, `dlt_pipelines/` included; `ty check` includes it too (`[tool.ty.src]` in `pyproject.toml`).

### 2. Validate Dagster definitions

```bash
just validate
```

Every dlt load is a Dagster asset. Validation loads the `dlt` location, imports every `pipelines.py`, and resolves every `defs.yaml`. A broken import, a renamed `source` or `pipeline`, or a `defs.yaml` pointing at the wrong module all fail here, before anything runs.

### 3. Run tests

```bash
just test
```

### 4. Check the dbt side

A new source needs `sources/src_<source>.yml` (the `schema` expression copied from `src_knmi.yml`, `identifier: <source>__<entity>`, `config.meta.dagster.asset_key: ["dlt", "ingest", "<source>", "<entity>"]`) and a staging model; see [expose it to dbt](../development/adding-dlt-loads.md). Confirm the references resolve:

```bash
just dbt parse
```

### 5. Run it

```bash
just dlt run <source>
```

Needs your `.env`. Prefer this over ad-hoc Python: it uses the same objects Dagster does.

### 6. Full validation

```bash
just pre-commit
```

## Related pages

- [Ingestion](../architecture/ingestion.md): sources, the destination, dispositions, state
- [Adding a dlt load](../development/adding-dlt-loads.md): the how-to, including the dbt source and staging model
- [Layer](../concepts/layer.md): what the source layer is for
- [Orchestration](../architecture/orchestration.md): the `dlt` code location and its job
- [Dagster agent guide](dagster.md): the component and how the location loads it
- [Snowflake agent guide](snowflake.md): the settings object behind the destination and the schema rule
- [Environment variables](../reference/environment-variables.md): `ENVIRONMENT`, `RUNTIME__LOG_LEVEL`, `DLT_PROJECT_DIR`, `DLT_DATA_DIR`
