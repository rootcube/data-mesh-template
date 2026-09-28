---
icon: material/play-circle
---

# First run

## Start Dagster

```bash
just start
```

runs `dagster dev` in the foreground (++ctrl+c++ stops it) with `DAGSTER_HOME=.dagster`, so run
history survives a restart. Open <http://localhost:3000>. Under *Deployment* you should see two
code locations, both loaded:

| Location | Owns |
|----------|------|
| `dlt` | Every dlt ingest pipeline under `dlt_pipelines/pipelines/ingest/`, plus, per source, a job and its daily schedule (stopped in `dev`), and a job for all with an opt-in schedule |
| `dbt_example` | The `dbt_example` dbt project, including the shared `dbt_common` models it builds, plus the jobs, freshness schedule and freshness sensor every dbt location gets, stopped in `dev` |

A location that failed to load shows the error right there; the terminal has the full trace.
`just validate` loads the same locations without the UI.

## Materialize the KNMI load

The starter source is the KNMI weather API: public, no credentials, small (seven stations, the
last 30 days, hourly).

1. *Assets*, search `climate_hourly` (key `dlt/ingest/knmi/climate_hourly`, group `dlt/ingest/knmi`).
2. **Materialize**, or launch the source's `job__dlt__ingest_<source>` under *Jobs*, which
   materializes every asset of the source. The run fetches the observations and merges them into
   `knmi__climate_hourly` in your personal source schema `DBT_<USERNAME>_SRC`, through your own
   load stage `DBT_<USERNAME>_SRC.ST_DEFAULT`.
3. Count what landed:

    ```bash
    just sf query "SELECT COUNT(1) FROM DBT_<USERNAME>_SRC.knmi__climate_hourly"
    ```

The same pipeline runs without Dagster, which is handy while developing a source:

```bash
just dlt run knmi
```

`just dlt list` shows every source; `--full-refresh` drops the source's tables and state before
loading.

## Build the dbt models

In the asset graph, `dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly` hangs directly
under the dlt asset: the dbt source declares the dlt asset key, so the lineage runs across the two
code locations. Select the dbt assets and materialize, or from the terminal:

```bash
just dbt build
```

`dbt build` seeds, runs and tests everything in `dbt_example`, including the calendar, time and
environment dimensions from `dbt_common`. Every run opens with a run-info banner (links to the
query history in Snowsight) and closes with a summary; run metadata lands in the `pre__dbt__*`
tables of your metadata schema.

!!! note "`int__common__holiday` needs Anaconda packages"
    That `dbt_common` model is a Python (Snowpark) model that imports `holidays` from Snowflake's
    Anaconda channel. If it fails with a package error, an `ORGADMIN` has not accepted the
    Anaconda terms yet. Ask your administrator, or disable the model; see
    [Troubleshooting](troubleshooting.md).

## Let it run by itself

Everything you just did by hand is automated too, and switched off in `dev` so that a laptop never
loads or builds on its own. Under *Automation* you find a daily schedule per dlt source and, per
dbt project, an hourly freshness schedule and a freshness sensor, all stopped. To watch the chain
once: launch the project's `job__<project>__source_freshness` from *Jobs*, then start its sensor.
The next tick sees every source as fresher than anything in its cursor and launches
`job__<project>__build_fresher` for their downstream. Stop the sensor again when you are done.
What these are named and why: [Orchestration](../understand/orchestration.md#jobs).

## What you now have in Snowflake

Everything sits in `DB_EXAMPLE_DEV`, in schemas prefixed with your `SNOWFLAKE_SCHEMA`:

| Schema | Written by | Holds |
|--------|------------|-------|
| `DBT_<USERNAME>_SRC` | dlt | `knmi__climate_hourly`, the API rows as loaded; the load files in the stage `ST_DEFAULT` |
| `DBT_<USERNAME>_REF` | `dbt seed` | the `dbt_common` seeds `seed_environment`, `seed_month`, `seed_unknown`, `seed_weekday` and the project's own `seed_knmi_station`, `seed_knmi_measurement_type` |
| `DBT_<USERNAME>_STG` | dbt | `stg__knmi__climate_hourly` and the `stg__seed__*` models |
| `DBT_<USERNAME>_INT` | dbt | the `int__common__*` and `int__weather__*` models |
| `DBT_<USERNAME>_MRT` | dbt | `dim__common__calendar`, `dim__common__time`, `dim__common__environment`, `dim__weather__knmi_station`, `dim__weather__knmi_measurement_type`, `fct__weather__knmi_measurement` |
| `DBT_<USERNAME>_EXP` | dbt | `exp__weather__station_weather`, the view consumers read |
| `DBT_<USERNAME>_MTD` | the `dbt_common` `on-run-end` hook | `pre__dbt__*` run metadata |
| `DBT_<USERNAME>_TMP` | dbt tests | stored test failures |

`just sf check` lists the schemas. In the shared environments the same objects live in the
provisioned `_SRC`, `_STG`, ... schemas instead; see [Layer](../understand/layer.md) and
[Environment](../understand/environment.md).

## Where things live locally

| Path | Contents |
|------|----------|
| `.dagster/` | `DAGSTER_HOME`: run history, event logs, and the versioned `dagster.yaml` (telemetry off, runs start immediately with no concurrency limit) |
| `.dlt/data/` | dlt working directory (pipeline state restores from Snowflake anyway) |
| `.dlt/config.toml` | dlt runtime settings, versioned |
| `src/orchestrator/defs/.local_defs_state/` | Dagster's component cache, written when `dagster dev` loads a location |
| `dbt/<project>/target/` | Compiled SQL and `manifest.json` |
| `dbt/<project>/logs/` | dbt's own log |
| `dbt/<project>/packages/` | The `dbt_common` package `dbt deps` installs |
| `logs/` | `dbt.log` from a dbt run started outside a project directory |
| `.cache/` | The docs build cache (`just docs`) |

Everything except `.dagster/dagster.yaml` and `.dlt/config.toml` is git-ignored state and safe to
delete; git brings those two back, and losing the rest only resets your local run history.
`just reset-local` does it in one go: it removes every path above except the two versioned config
files and `packages/` (which `dbt deps` refreshes anyway), recreates `.dagster/` and `.dlt/data/`,
and reruns `dbt deps` and `dbt parse`. Stop `just start` first.

## Stopping

++ctrl+c++ in the terminal running `just start`. `just start` stops a forgotten instance itself,
and `just stop` does the same on its own.

Ready to change things? [Build](../build/index.md). Want the model behind the names first?
[Understand](../understand/index.md).
