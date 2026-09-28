---
icon: material/download-network
---

# Ingestion (dlt)

Data enters the platform through [dlt](https://dlthub.com/docs) pipelines. Every source is one
folder under `dlt_pipelines/pipelines/ingest/`, exposes a module-level `source` and `pipeline`,
and lands its tables in the source layer of the project database as `<source>__<entity>`.
Dagster turns each folder into assets through a `defs.yaml`; the same objects run standalone:

```bash
just dlt list          # knmi         dlt_pipelines.pipelines.ingest.knmi.pipelines
just dlt run knmi      # pipeline.run(source), prints the load info
```

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
:   A function that yields records for one table. `climate_hourly` yields one dict per station
    per hour. Its decorator carries the table name, the write disposition and the primary key.

Source
:   A group of resources that share a name and settings. The name is the source system, never
    one of its entities, because it also names the dlt schema and has to survive a second
    resource joining it. `max_table_nesting=0` keeps nested objects (should the API ever return
    any) in one table instead of child tables.

Pipeline
:   The runner: a name (`ingest_<source>`), a destination and a dataset, which is the Snowflake
    schema. `pipeline.run(source)` extracts, normalizes and loads.

```python title="dlt_pipelines/pipelines/ingest/knmi/pipelines.py"
SOURCE = "knmi"
ENTITY = "climate_hourly"


# The source (and so the dlt schema) is named after the source, not after one of its entities: a
# second resource joins it without renaming anything. The table name carries `<source>__<entity>`.
@dlt.source(name=SOURCE, max_table_nesting=0)
def knmi_source() -> Iterator[dlt.sources.DltResource]:
    """KNMI hourly observations for a handful of stations, last 30 days."""

    @dlt.resource(
        name=ENTITY,
        table_name=f"{SOURCE}__{ENTITY}",
        write_disposition="merge",
        primary_key=["station_code", "date", "hour"],
        # WW (weather code) and IX (how it was observed) are null in every row of a recent window,
        # so dlt cannot infer a type and drops the columns with a warning. Declare them instead.
        columns={"ww": {"data_type": "bigint"}, "ix": {"data_type": "bigint"}},
    )
    def climate_hourly() -> Iterator[dict]:
        yield from fetch_hourly_observations()

    yield climate_hourly()


source = knmi_source()

pipeline = dlt.pipeline(
    pipeline_name=pipeline_name(SOURCE),
    destination=destination(SOURCE),
    dataset_name=source_dataset(),
)
```

The names `source` and `pipeline` are a contract: `defs.yaml` and the standalone runner both
import the module and look for exactly those two attributes. The resource keeps the short name
`climate_hourly`, which becomes the last segment of the asset key, while `table_name` sets the
Snowflake table to `knmi__climate_hourly`, the convention that keeps one source-layer schema
tidy with many sources in it.

`source.py` is plain Python. It uses `dlt.sources.helpers.requests` (a `requests` session with
retries) to call the KNMI endpoint in chunks of ten days and yields the JSON records unchanged,
never reaching back past `START_DATE` (2026-01-01) whatever the window says. No renaming, no
casting: that happens in the dbt staging model. The chunks are headroom rather
than a current constraint: KNMI rejects a query over roughly 100k rows, the 30-day window is
some 4,900, and because the rejection arrives as an HTML page with HTTP 200 it would surface as
a JSON decode error rather than a failed status. A window that yields no rows at all raises,
because an empty load is otherwise invisible: dlt reports the package as loaded, the Dagster
materialization carries no row count, and the staging model's `has_data` test still passes on
the rows of the previous load.

## Merge, primary key, full refresh

The KNMI resource uses `write_disposition="merge"` with the primary key
`station_code, date, hour`. Every run pulls a 30-day window, so consecutive daily runs overlap
by 29 days; merge upserts on the key and the table stays free of duplicates. dlt adds
bookkeeping columns of its own, among them `_dlt_load_id`, the load package that wrote the row.

A merge needs a table to merge from, so dlt first `COPY`s each batch from the stage into a
staging table and then runs `MERGE` into the source table. By default those staging tables go
in a schema of dlt's own, `<dataset>_staging`, which nobody provisions and the ingest role may
not create. `snowflake_destination()` points `staging_dataset_name_layout` at the temporary
layer instead, where the ingest role holds `CREATE TABLE`
(`terraform/config/roles/ingest.yaml`). The tables are emptied after each successful load
(`truncate_staging_dataset` in `.dlt/config.toml`), so raw source rows do not linger where
analysts can read them. A failed load leaves them until the next successful one.

To start over, drop the source's tables and state in the destination before loading:

```bash
just dlt run knmi --full-refresh
```

That maps to `pipeline.run(source, refresh="drop_sources")` in `dlt_pipelines/__main__.py`.

## The destination and the dataset

Every pipeline gets its destination and its dataset from two functions. `destination()` returns
Snowflake, or the DuckDB file of the `local` environment when `SnowflakeSettings.is_local`:

```python title="dlt_pipelines/utils/destination.py"
--8<-- "dlt_pipelines/utils/destination.py"
```

`SnowflakeSettings.from_env()` reads the `SNOWFLAKE_*` variables and `ENVIRONMENT` from `.env`,
`dlt_credentials()` translates them into what dlt's Snowflake destination expects, and
`schema_for_layer("src")` applies the platform's schema rule: the shared `_SRC`, or your
personal source schema in `dev` and `local`
([Environment variables](../reference/environment-variables.md)). Credentials are only validated
when a Snowflake pipeline runs, so importing the pipelines, which Dagster does on every
code-location load, works without a `.env`; unset variables are logged as a warning while the
destination is built, because dlt's own error would name its field names
(`DESTINATION__SNOWFLAKE__CREDENTIALS__DATABASE`) rather than the platform's. The values are
read at import, so a change in `.env` only reaches a running UI after `just stop` and
`just start`.

In `dev` the pipeline runs as your engineer role. In a deployed environment it runs as the
project's ingest system role, `RL_<PROJECT>_<ENV>__ING`, the only role with write access to the
source layer there. See [Role](role.md).

### The load stage

dlt writes each load as JSONL files under `.dlt/data/`, uploads them with `PUT` and loads the
table with `COPY INTO`. `stage_name` decides where those files land: not the table's implicit
stage, but the internal stage `ST_DEFAULT` that Terraform creates in every source-layer schema
(`terraform/stages.tf`), next to the tables it loads. Inside it, `load_stage()` gives every
source a path that mirrors the asset key prefix, and every load a folder of its own:

```
dlt/ingest/knmi/ingest_knmi__1758700000.123456/knmi__climate_hourly.a1b2c3d4.0.jsonl
```

dlt itself would name that folder after the bare load id, in double quotes;
`snowflake_named_folders` (`dlt_pipelines/utils/snowflake_stage.py`) is dlt's Snowflake
destination with only that one detail changed. Its load job copies dlt's
`SnowflakeLoadJob.run`, so compare the two when upgrading dlt; `tests/test_dlt_pipelines.py`
pins the `PUT`, `COPY INTO` and `REMOVE` it runs. The file names stay dlt's, because `PUT`
keeps the name of the local file.

The files stay in the stage after a successful `COPY INTO` (`keep_staged_files`, dlt's default,
kept on purpose): the stage is the landing archive of what was loaded.
`LIST @_SRC.ST_DEFAULT/dlt/ingest/knmi/` shows every KNMI load and
`SELECT * FROM DIRECTORY(@_SRC.ST_DEFAULT)` reads the directory table, which internal stages
never refresh by themselves, which is why `dbt_common.refresh_stages()` runs
`ALTER STAGE ... REFRESH` at the start of every `dbt run` and `dbt build`.

Nothing prunes that archive, so prune it yourself when a source grows: `REMOVE` takes a path,
so `REMOVE @_SRC.ST_DEFAULT/dlt/ingest/knmi/` drops one source's load files and a single
`.../knmi/ingest_knmi__<load id>/` folder drops one load. Setting
`DESTINATION__SNOWFLAKE__KEEP_STAGED_FILES=false` has dlt delete each file right after its
`COPY INTO` instead, trading the archive for nothing to clean up.

### Runtime settings

There are no dlt secrets files. `.dlt/config.toml` holds runtime settings only: telemetry off,
log level `WARNING`, four extract workers, two each for normalize and load (laptop-sized on
purpose), and `truncate_staging_dataset`. dlt finds the file because the justfile and `.envrc`
set `DLT_PROJECT_DIR` to the repository root; `DLT_DATA_DIR` points at `.dlt/data/`, the
git-ignored working directory that `just init` recreates. Set `RUNTIME__LOG_LEVEL=INFO` in
`.env` to see each extract, normalize and load step.

## The Dagster component

`defs.yaml` next to the pipeline declares a `DltLoadCollectionComponent`. Each `loads` entry
points at the module-level objects and says how to translate dlt resources into Dagster assets:

```yaml title="dlt_pipelines/pipelines/ingest/knmi/defs.yaml"
--8<-- "dlt_pipelines/pipelines/ingest/knmi/defs.yaml"
```

`deps: []` matters: without it the component invents a placeholder upstream asset for every
resource, and the graph starts one node too early. The API is the start.

!!! warning "Keep the Python next to the `defs.yaml`"
    The `.pipelines.pipeline` references resolve relative to the folder that holds the
    `defs.yaml`, not to the package root. Move `pipelines.py` elsewhere and the component
    breaks, however plausible the import path looks.

The `dlt` code location (`src/orchestrator/locations/dlt/definitions.py`) loads the whole
`dlt_pipelines` package as a component tree, so every `defs.yaml` under it is picked up without
registration. One dlt resource becomes one asset; materializing it runs the pipeline for that
resource.

| Artifact | Value |
|----------|-------|
| Asset key | `dlt/ingest/<source>/<entity>`: `dlt/ingest/knmi/climate_hourly` |
| Group | `dlt/ingest/<source>` |
| Kinds | `dlt`, `snowflake` |
| Jobs | `job__dlt__ingest_<source>` selects `dlt/ingest/<source>`, one per source folder; `job__dlt__ingest_all` selects every key under `dlt/ingest`, so new sources join it for free |
| Schedules | `schedule__dlt__ingest_<source>` runs the source's job daily at 06:00 UTC, stopped by default in `dev`; `schedule__dlt__ingest_all` is the opt-in for one run of everything, stopped everywhere |
| Snowflake table | `<source-layer schema>.<source>__<entity>`: `_SRC.knmi__climate_hourly` |
| Stage path | `<source-layer schema>.ST_DEFAULT/dlt/ingest/<source>/`, then a folder per load, `<pipeline>__<load id>` |

The asset key is what links ingestion to transformation. The dbt source in
`dbt/dbt_example/sources/src_knmi.yml` declares the same key under
`config.meta.dagster.asset_key`, and Dagster draws the edge to
`dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly` across the two code locations. See
[Orchestration](orchestration.md#lineage-across-code-locations).

## The standalone runner

While developing a source you do not want to click through a UI. `python -m dlt_pipelines`
discovers every package under `pipelines/ingest/` and runs one of them, importing
`<source>.pipelines` and calling `pipeline.run(module.source)`: the same objects Dagster uses.
The Dagster equivalent is `job__dlt__ingest_<source>`, which the dlt location derives from the
same `discover()`. Both share the pipeline state stored in the destination, so mixing them is
fine.

## Related pages

- [Adding a dlt load](../build/adding-dlt-loads.md): a second source, step by step
- [Layer](layer.md): what the source layer contains and who reads it
- [Snowflake](snowflake.md): the settings reader behind the destination
