---
icon: material/download-network
---

# Ingestion (dlt)

Data enters the platform through [dlt](https://dlthub.com/docs) pipelines. Every source is one
folder under `dlt_pipelines/pipelines/ingest/`, exposes a module-level `source` and `pipeline`,
and lands its tables in the source layer of the project database as `<source>__<entity>`.
Dagster turns each folder into assets through a `defs.yaml`; the same objects run standalone
with `just dlt run <source>`.

## Anatomy of a source

```
dlt_pipelines/pipelines/ingest/knmi/
├── __init__.py
├── constants.py     # URL, station list, window and chunk sizes
├── source.py        # the HTTP calls: fetch_hourly_observations() yields dicts
├── pipelines.py     # the dlt objects: `source` and `pipeline`
└── defs.yaml        # the Dagster component that turns them into assets
```

Three dlt concepts map onto `pipelines.py`:

Resource
:   A function that yields records for one table. `climate_hourly` yields one dict per
    station per hour. Its decorator carries the table name, the write disposition and the
    primary key.

Source
:   A group of resources that share a name and settings. `knmi_source()` yields the single
    resource; `max_table_nesting=0` keeps nested objects (should the API ever return any) in
    one table instead of splitting them into child tables.

Pipeline
:   The runner: a name, a destination and a dataset (the Snowflake schema).
    `pipeline.run(source)` extracts, normalizes and loads.

```python title="dlt_pipelines/pipelines/ingest/knmi/pipelines.py"
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

The names `source` and `pipeline` are a contract: `defs.yaml` and the standalone runner both
import the module and look for exactly those two attributes. The resource keeps the short
name `climate_hourly` (it becomes the last segment of the asset key) while `table_name` sets
the Snowflake table to `knmi__climate_hourly`, the `<source>__<entity>` convention that keeps
one source-layer schema tidy with many sources in it.

`source.py` is plain Python. It uses `dlt.sources.helpers.requests` (a `requests` session with
retries) to call the KNMI endpoint in chunks of ten days, because the API rejects requests that
span too many rows, and yields the JSON records unchanged. No renaming, no casting: that
happens in the dbt staging model.

## Merge, primary key, full refresh

The KNMI resource uses `write_disposition="merge"` with the primary key
`station_code, date, hour`. Every run pulls a 30-day window, so consecutive daily runs overlap
by 29 days; merge upserts on the key and the table stays free of duplicates. dlt adds
bookkeeping columns of its own, among them `_dlt_load_id`, the load package that wrote the
row.

To start over, drop the source's tables and state in the destination before loading:

```bash
just dlt run knmi --full-refresh
```

This maps to `pipeline.run(source, refresh="drop_sources")` in `dlt_pipelines/__main__.py`.

## The Snowflake destination and the dataset

Every pipeline gets its destination and its dataset from two functions:

```python title="dlt_pipelines/utils/destination.py"
SOURCE_LAYER = "src"
STAGE = "ST_DLT"


def snowflake_destination() -> Destination:
    settings = SnowflakeSettings.from_env()
    return dlt.destinations.snowflake(credentials=settings.dlt_credentials(), stage_name=load_stage(settings))


def load_stage(settings: SnowflakeSettings) -> str:
    return f"{settings.database}._{SOURCE_LAYER.upper()}.{STAGE}"


def source_dataset() -> str:
    return SnowflakeSettings.from_env().schema_for_layer(SOURCE_LAYER)
```

`SnowflakeSettings.from_env()` reads the `SNOWFLAKE_*` variables and `ENVIRONMENT` from `.env`.
`dlt_credentials()` translates them into what dlt's Snowflake destination expects: the account
identifier, user name, private key path and passphrase, role, warehouse and database.
`schema_for_layer("src")` applies the platform's schema rule: the dataset is `_SRC` in the
shared environments and `<SNOWFLAKE_SCHEMA>_SRC` (for example `DBT_USERNAME_SRC`) in `dev`, where
dlt creates it on first load.

`stage_name` is where the load files go. dlt writes each load as JSONL files under
`.dlt/data/`, uploads them with `PUT` and loads the table with `COPY INTO`. Without a
`stage_name` it would use the table's implicit stage; here it uses the internal stage
`ST_DLT` that Terraform creates in the provisioned source layer of every project database
(`terraform/stages.tf`), so the files of every load are in one place per environment:
`DB_EXAMPLE_DEV._SRC.ST_DLT`, with a folder per load id. It is the same stage in `dev`, where
only the tables move to your personal schema. The ingest role holds `READ` and `WRITE` on it
(`READ ON STAGES`, `WRITE ON STAGES` in `terraform/config/roles/ingest.yaml`), and the engineer
role inherits that in `dev`. dlt keeps the files after a successful `COPY INTO`
(`keep_staged_files`, its default); `LIST @_SRC.ST_DLT` shows them, `REMOVE` cleans up. The
stage has a directory table, so `SELECT * FROM DIRECTORY(@_SRC.ST_DLT)` works too. Internal
stages do not refresh it automatically; `dbt_common.refresh_stages()` runs
`ALTER STAGE _SRC.ST_DLT REFRESH` at the start of every `dbt run` and `dbt build`.

Credentials are only validated when a pipeline runs, so importing the pipelines (which Dagster
does on every code-location load) works without a `.env`. In `dev` the pipeline runs as your
engineer role; in a deployed environment it runs as the project's ingest system role
(`RL_<PROJECT>_<ENV>__ING`), which is the only role with write access to `_SRC` there. See
[Role](../concepts/role.md).

There are no dlt secrets files. `.dlt/config.toml` holds runtime settings only:

```toml title=".dlt/config.toml"
[runtime]
dlthub_telemetry = false
log_level = "WARNING"  # RUNTIME__LOG_LEVEL in .env overrides this for local runs

[extract]
workers = 4

[normalize]
workers = 2

[load]
workers = 2
```

dlt finds this file because the justfile and `.envrc` set `DLT_PROJECT_DIR` to the repository
root; `DLT_DATA_DIR` points at `.dlt/data/`, the git-ignored working directory. Set
`RUNTIME__LOG_LEVEL=INFO` in `.env` to see each extract, normalize and load step.

## The Dagster component

`defs.yaml` next to the pipeline declares a `DltLoadCollectionComponent`. Each `loads` entry
points at the module-level objects (relative to the folder the file is in) and says how to
translate dlt resources into Dagster assets:

```yaml title="dlt_pipelines/pipelines/ingest/knmi/defs.yaml"
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

`deps: []` matters: without it the component would invent a placeholder upstream asset for
every resource, and the graph would start one node too early. The API is the start.

The `dlt` code location (`src/orchestrator/locations/dlt/definitions.py`) loads the whole
`dlt_pipelines` package as a component tree, so every `defs.yaml` under it is picked up
automatically. One dlt resource becomes one asset; materializing it runs the pipeline for that
resource.

| Artifact | Value |
|----------|-------|
| Asset key | `dlt/ingest/<source>/<entity>`: `dlt/ingest/knmi/climate_hourly` |
| Group | `dlt/ingest/<source>` |
| Kinds | `dlt`, `snowflake` |
| Job | `job_dlt_ingest_all` selects every key under `dlt/ingest`, so new sources join it for free |
| Snowflake table | `<source-layer schema>.<source>__<entity>`: `_SRC.knmi__climate_hourly`, or `DBT_USERNAME_SRC.knmi__climate_hourly` in `dev` |

The asset key is what links ingestion to transformation. The dbt source in
`dbt/dbt_example/sources/src_knmi.yml` declares the same key under
`config.meta.dagster.asset_key`, and Dagster draws the edge to
`dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly` across the two code locations. See
[Orchestration](orchestration.md#lineage-across-code-locations).

## The standalone runner

While developing a source you do not want to click through the UI. `python -m dlt_pipelines`
discovers every package under `pipelines/ingest/` and runs one of them:

```bash
just dlt list          # knmi         dlt_pipelines.pipelines.ingest.knmi.pipelines
just dlt run knmi      # pipeline.run(source), prints the load info
```

The runner imports `<source>.pipelines` and calls `pipeline.run(module.source)`, the same
objects Dagster uses. Dagster runs and standalone runs share the pipeline state stored in the
destination, so mixing them is fine.

## Related pages

- [Adding a dlt load](../development/adding-dlt-loads.md): a second source, step by step
- [Layers in practice](layers.md#source-what-dlt-landed): what the source layer contains and who reads it
- [Snowflake](snowflake.md): the settings reader behind the destination
