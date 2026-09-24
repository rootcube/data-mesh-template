---
icon: material/play-circle
---

# First run

## Start Dagster

```bash
just start
```

runs `dagster dev` in the foreground (++ctrl+c++ stops it) with `DAGSTER_HOME=.dagster`, so run
history survives restarts. Open <http://localhost:3000>. Under *Deployment* you should see two
code locations, both loaded:

| Location | Owns |
|----------|------|
| `dlt` | Every dlt ingest pipeline under `dlt_pipelines/pipelines/ingest/`, plus the job `job_dlt_ingest_all` |
| `dbt_example` | The `dbt_example` dbt project, including the shared `dbt_common` models it builds, plus the job `job_dbt_example_build_all` |

A location that failed to load shows the error right there; the terminal has the full trace.
`just validate` loads the same locations without the UI.

## Materialize the KNMI load

The starter source is the KNMI weather API: public, no credentials, small (seven stations, the
last 30 days, hourly).

1. *Assets*, search `climate_hourly` (key `dlt/ingest/knmi/climate_hourly`, group `dlt/ingest/knmi`).
2. **Materialize**. The run fetches the observations and merges them into the table
   `knmi__climate_hourly` in your personal source schema `DBT_<NAME>_SRC`, creating the schema
   on first use.
3. Check:

    ```bash
    just snowflake query "SELECT COUNT(*) FROM DBT_<NAME>_SRC.knmi__climate_hourly"
    ```

The same pipeline runs without Dagster, which is handy while developing a source:

```bash
just dlt run knmi
```

`just dlt list` shows every source; `--full-refresh` drops the source's tables and state before
loading.

## Build the dbt models

In the asset graph, `dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly` hangs directly under the dlt asset: the dbt
source declares the dlt asset key, so the lineage runs across the two code locations. Select
the dbt assets and materialize, or from the terminal:

```bash
just dbt build
```

`dbt build` seeds, runs and tests everything in `dbt_example`, including the calendar, time
and environment dimensions from `dbt_common`. Every run starts with a run-info banner (links
to the query history in Snowsight) and ends with a summary; run metadata lands in the
`pre__dbt__*` tables of your metadata schema.

!!! note "`int__common__holiday` needs Anaconda packages"
    That `dbt_common` model is a Python (Snowpark) model that imports `holidays` from
    Snowflake's Anaconda channel. If it fails with a package error, an `ORGADMIN` has not
    accepted the Anaconda terms yet. Ask your administrator, or disable the model; see
    [Troubleshooting](troubleshooting.md).

## What you now have in Snowflake

Everything sits in `DB_EXAMPLE_DEV`, in schemas prefixed with your `SNOWFLAKE_SCHEMA`:

| Schema | Written by | Holds |
|--------|------------|-------|
| `DBT_<NAME>_SRC` | dlt | `knmi__climate_hourly`, the API rows as loaded |
| `DBT_<NAME>_REF` | `dbt seed` | the `dbt_common` seeds: `seed_environment`, `seed_month`, `seed_unknown`, `seed_weekday` |
| `DBT_<NAME>_STG` | dbt | `stg__knmi__climate_hourly` and the `stg__seed__*` models |
| `DBT_<NAME>_INT` | dbt | the `int__common__*` models |
| `DBT_<NAME>_MRT` | dbt | `dim__common__calendar`, `dim__common__time`, `dim__common__environment` |
| `DBT_<NAME>_EXP` | dbt | nothing yet: `models/05_exp/` is empty in the starter |
| `DBT_<NAME>_MTD` | the `dbt_common` `on-run-end` hook | `pre__dbt__*` run metadata |
| `DBT_<NAME>_TMP` | dbt tests | stored test failures |

`just snowflake check` lists the schemas. In `prd` (and `tst`, `acc` once enabled) the same
objects live in the provisioned `_SRC`, `_STG`, ... schemas; see [Layer](../concepts/layer.md).

## Where things live locally

| Path | Contents |
|------|----------|
| `.dagster/` | `DAGSTER_HOME`: run history, event logs, and the versioned `dagster.yaml` (telemetry off, at most 4 concurrent runs) |
| `.dlt/data/` | dlt working directory (pipeline state restores from Snowflake anyway) |
| `.dlt/config.toml` | dlt runtime settings, versioned |
| `dbt/<project>/target/` | Compiled SQL and `manifest.json` |
| `dbt/<project>/logs/` | dbt's own log |

Everything except `.dagster/dagster.yaml` and `.dlt/config.toml` is git-ignored state and safe
to delete; git brings the two config files back, and deleting the rest only resets your local
run history.

## Stopping

++ctrl+c++ in the terminal running `just start`. `just start` stops a forgotten instance
first, and `just stop` does the same on its own.

Ready to change things? Head to [Development](../development/index.md). Want the model behind
the names first? [Concepts](../concepts/index.md).
