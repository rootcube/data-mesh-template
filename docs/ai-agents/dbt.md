---
icon: material/database-cog
---

# dbt

Agent guide for the dbt layer: where a change belongs, how `dbt_common` and a project fit together, how schemas follow the environment, the model and test pattern to copy, and the validation loop to run before presenting work. The rules themselves (layers, naming, testing, style) live on the canonical pages linked below; this page routes you to them and adds the operational workflow.

## Orientation

Two things live under `dbt/`, sharing one `profiles.yml` and one `.sqlfluff`:

| Folder | What it is | Verdict for new work |
|---|---|---|
| `dbt/dbt_example/` | The project of the `example` mesh node. Layers `02_stg`, `03_int`, `04_mrt`, `05_exp`, plus `sources/`, `seeds/`, `tests/`, `macros/`. | **Default.** New models for this project go here. A new mesh node gets its own copy: [adding a project](../development/adding-projects.md). |
| `dbt/dbt_common/` | A package every project installs (`packages.yml`: `local: ../dbt_common`). Shared macros, generic models and seeds, generic tests. | Shared machinery only, not a home for project models. |

`scripts/dbt_all.py` (behind `just dbt-all`) runs one dbt command in every project under `dbt/` and skips `dbt_common` on purpose: a package is built through the project that installs it.

!!! note "Profile, targets and `DBT_PROFILES_DIR`"
    Both use the `default` profile in `dbt/profiles.yml`. The target follows `ENVIRONMENT` (`dev`, `tst`, `acc`, `prd`) unless `DBT_TARGET` overrides it. The four Snowflake targets read the same `SNOWFLAKE_*` variables and authenticate with a key pair: your own in `dev`, the transform system user's elsewhere. `dev` defaults `schema` to `DBT` and runs 8 threads; `tst`, `acc` and `prd` default `schema` to `_TMP` and run 16. The `dummy` target is an in-memory DuckDB (`dbt-duckdb`) that never touches Snowflake: CI, pre-commit and sqlfluff use it to parse and render SQL. `just dbt ...` runs inside `dbt/dbt_example` with `DBT_PROFILES_DIR` set to `dbt/`; `just project=dbt_x dbt ...` targets another project. In a bare shell, `.envrc` sets the same variables for direnv users.

## Where the rules live

Consult these pages instead of relying on memory; they are the single source of truth:

| Topic | Canonical page |
|---|---|
| The layers as a concept, what each one is for | [Layer](../concepts/layer.md) |
| Layer architecture, the schema per layer, the "reference only the layer directly below" rule | [Layers in practice](../architecture/layers.md) |
| Model design per layer, `_conf/` placement, required config, tests, docs, seeds, macros | [dbt style guide](../conventions/dbt-style-guide.md) |
| Model, column, source, seed and test naming | [Naming](../conventions/naming.md) |
| Step-by-step workflow for a new model | [Adding a dbt model](../development/adding-dbt-models.md) |
| Step-by-step workflow for a new project (Terraform YAML, dbt copy, code location, the `dbt_common` opt-out) | [Adding a project](../development/adding-projects.md) |
| dbt tests, `just validate`, what CI checks | [Testing](../development/testing.md) |
| SQL formatting and the sqlfluff rules | [SQL style](../conventions/sql-style.md) and the [SQL agent guide](sql.md) |
| How Dagster loads the project | [Transformation](../architecture/transformation.md) and the [Dagster agent guide](dagster.md) |
| Every dbt passthrough recipe | [Command reference](../reference/commands.md) |

## How the projects are wired

Facts from `dbt/dbt_example/dbt_project.yml` and `dbt/dbt_common/dbt_project.yml` that shape every change:

Schemas follow the environment
:   Layer folders carry a `+schema`: `02_stg` is `stg`, `03_int` is `int`, `04_mrt` is `mrt`, `05_exp` is `exp`; seeds get `ref`, stored test failures `tmp` (`+store_failures: true`), run metadata `mtd`. `dbt_common.generate_schema_name` turns that into the schema of the project database `DB_<PROJECT>_<ENV>`: `_<LAYER>` (`_STG`) in `tst`, `acc` and `prd`, and `<target.schema>_<LAYER>` (`DBT_INFO_STG`) in `dev` and `dummy`, so several engineers share one development database. A model without a `+schema` lands in `target.schema` itself (`SNOWFLAKE_SCHEMA`). Never spell a schema out in a model.

Materialization defaults
:   `dbt_example`: tables for STG, INT and MRT, views for EXP (`+materialized: view` at project level). `dbt_common`: tables for its STG and MRT models, views for INT. Every layer folder also gets a tag `layer=<code>`, and `persist_docs` is on for relations and columns. Override per model in the config block only when there is a reason.

Dispatch
:   `dispatch: search_order: ["dbt_common", "dbt"]` in the project makes dbt pick up the package's overrides of `generate_schema_name` and `set_query_tag`. A new project must copy that block or its schemas come out wrong outside `dev`.

Hooks
:   `on-run-start` calls `dbt_common.log_run_info()` (a banner with links to the query history in Snowsight). `dbt_common`'s own `on-run-end` hooks run in every project that installs it: `upload_results` writes run metadata into `pre__dbt__*` tables in the metadata layer (`_MTD`, or `<prefix>_MTD` in `dev`) for `run`, `build`, `test`, `seed` and `freshness`, skipped on the `dummy` target; then `log_run_summary` prints totals, slowest models and failed tests.

The `dbt_common` models
:   `models: dbt_common: +enabled: true` in `dbt_example` builds the shared seeds (`seed_environment`, `seed_month`, `seed_unknown`, `seed_weekday`), the staging models over them (`stg__seed__*`), `int__common__{date,calendar,holiday,time,environment}` and `dim__common__{calendar,time,environment}`.

Generic tests
:   `dbt/dbt_common/tests/generic/` ships four tests: `has_data` and `rows_expected` on a model, `not_empty` and `not_negative` on a column. From a project they are called namespaced (`dbt_common.has_data`); `has_data` sets `store_failures=false` because its failure row is a constant.

!!! danger "Exactly one project builds the `dbt_common` models"
    Each dbt project is its own Dagster code location. Two projects that both build `dim__common__calendar` get distinct asset keys (`<project>/packages/dbt_common/models/04_mrt/common/dim__common__calendar`) but write the same table into the one database `.env` points at. Every project after the first sets `models: dbt_common: +enabled: false` (the opt-out documented in `dbt_common/dbt_project.yml`).

!!! warning "`int__common__holiday` is a Python model"
    It runs as Snowpark inside Snowflake and imports the `holidays` package from the Anaconda channel, which an `ORGADMIN` has to accept once per account. The country comes from the `holiday_country` var (`vars:` in the project's `dbt_project.yml`, `NL` by default). If it fails with a package error, ask a platform administrator or disable the model in `dbt/dbt_example/dbt_project.yml`; the snippet is in [Snowflake provisioning](../administration/snowflake-provisioning.md).

## The staging pattern

Copy the one staging model that exists. Source, SQL and YAML together:

=== "Source"

    `dbt/dbt_example/sources/src_knmi.yml`, abridged. The `schema` line repeats the `generate_schema_name` rule with `env_var` (source YAML cannot call macros), `identifier` is the dlt table `<source>__<entity>`, and `config.meta.dagster.asset_key` is what makes the Dagster lineage run from the dlt asset into this model.

    ```yaml
    version: 2

    sources:
      - name: knmi
        # The source layer: _SRC, or <SNOWFLAKE_SCHEMA>_SRC in dev (same rule as dbt_common's
        # generate_schema_name; source YAML can only use env_var, not macros).
        schema: "{{ env_var('SNOWFLAKE_SCHEMA', '') if env_var('ENVIRONMENT', 'dev') in ['dev', 'dummy'] else '' }}_SRC"
        tables:
          - name: climate_hourly
            identifier: knmi__climate_hourly
            description: One row per station per hour (hour 1..24 = the hour ending at that time).
            config:
              meta:
                dagster:
                  # Same key as the dlt asset, so the Dagster lineage runs dlt -> dbt.
                  asset_key: ["dlt", "ingest", "knmi", "climate_hourly"]
            columns:
              - name: station_code
                description: KNMI station number (260 = De Bilt, 370 = Eindhoven, ...).
    ```

=== "Model"

    `dbt/dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly.sql`, in full: config block first, one `cte_` CTE over the source, every table named with `AS`, typed and renamed columns in the final `SELECT`.

    ```sql
    {{
        config(
            materialized='table',
            unique_key=['station_code', 'observed_at']
        )
    }}

    -- KNMI hourly observations, typed and converted to SI-ish units. The API's hour 1..24 is the
    -- hour *ending* at that time, so hour 24 of 2024-01-01 becomes 2024-01-02 00:00.
    WITH cte_source AS (

      SELECT
        src.station_code
      , src.date
      , src.hour
      , src.t
      , src.fh
      , src.rh
      , src.q
      , src.u
      , src._dlt_load_id
      FROM
        {{ source('knmi', 'climate_hourly') }} AS src

    )

    SELECT
      CAST(obs.station_code AS INTEGER)                                                         AS station_code
    , DATEADD('hour', CAST(obs.hour AS INTEGER), CAST(CAST(obs.date AS DATE) AS TIMESTAMP_NTZ)) AS observed_at
    , CAST(obs.t AS INTEGER) / 10.0                                                             AS temperature_celsius
    , CAST(obs.fh AS INTEGER) / 10.0                                                            AS wind_speed_ms
    , CASE
        WHEN CAST(obs.rh AS INTEGER) = -1 THEN 0.05
        ELSE CAST(obs.rh AS INTEGER) / 10.0
      END                                                                                       AS precipitation_mm
    , CAST(obs.q AS INTEGER)                                                                    AS global_radiation_jcm2
    , CAST(obs.u AS INTEGER)                                                                    AS relative_humidity_pct
    , obs._dlt_load_id
    FROM
      cte_source AS obs
    ```

=== "YAML"

    `dbt/dbt_example/models/02_stg/knmi/_conf/stg__knmi__climate_hourly.yml`, in full. One file per model, in the sibling `_conf/` folder: a description and `data_type` per column, every test named `<model>__<column>__<test>`.

    ```yaml
    version: 2

    models:
      - name: stg__knmi__climate_hourly
        description: Typed KNMI hourly observations, one row per station per hour.

        data_tests:
          - dbt_common.has_data:
              name: stg__knmi__climate_hourly__has_data

          - dbt_utils.unique_combination_of_columns:
              name: stg__knmi__climate_hourly__station_code__observed_at__unique
              arguments:
                combination_of_columns: [station_code, observed_at]

        columns:
          - name: station_code
            description: KNMI station number.
            data_type: integer
            data_tests:
              - not_null:
                  name: stg__knmi__climate_hourly__station_code__not_null

          - name: observed_at
            description: End of the observation hour (timestamp, no timezone).
            data_type: timestamp_ntz
            data_tests:
              - not_null:
                  name: stg__knmi__climate_hourly__observed_at__not_null

          - name: temperature_celsius
            description: Air temperature at 1.50 m.
            data_type: number

          - name: wind_speed_ms
            description: Hourly mean wind speed in m/s.
            data_type: number

          - name: precipitation_mm
            description: Hourly precipitation in mm.
            data_type: number
            data_tests:
              - dbt_common.not_negative:
                  name: stg__knmi__climate_hourly__precipitation_mm__not_negative

          - name: global_radiation_jcm2
            description: Global radiation in J/cm2.
            data_type: integer

          - name: relative_humidity_pct
            description: Relative humidity in percent.
            data_type: integer

          - name: _dlt_load_id
            description: dlt load package that wrote the source row.
            data_type: varchar
    ```

Renames, casts and unit conversions belong here, in staging; dlt mirrors the API. Which config keys and tests each layer needs: [dbt style guide](../conventions/dbt-style-guide.md).

## Package macros

Package macros resolve namespaced: call `dbt_common.utc_today()`, never bare `utc_today()`. The ones you will reach for:

| Macro | Use |
|---|---|
| `dbt_common.utc_now()` / `dbt_common.utc_today()` | Session-timezone-proof "now" and "today" (`SYSDATE()` based); use instead of `CURRENT_TIMESTAMP` / `CURRENT_DATE` |
| `dbt_common.search_optimization(this)` | Post-hook that adds search optimization to a table or incremental model; renders nothing for views |
| `dbt_common.format_duration(seconds)` | Seconds to `HH:MM:SS` |
| `dbt_utils.*` | `dbt-labs/dbt_utils` (`>=1.3.0, <2.0.0`) is installed in `dbt_example`; `dbt_utils.unique_combination_of_columns` is the multi-column uniqueness test |

The full macro table with the Snowflake-facing ones (`generate_schema_name`, `set_query_tag`, run logging, the metadata upload): [Snowflake](snowflake.md#shared-macros).

## Packages

`dbt/dbt_example/packages.yml`: `local: ../dbt_common` and `dbt-labs/dbt_utils`. `dbt/dbt_common/packages.yml` is deliberately empty: a dependency added there does not propagate to consuming projects (each project's `package-lock.yml` hashes only its own `packages.yml`), so every project declares `dbt_utils` itself. Run `dbt deps` after cloning and after any `packages.yml` change; `just init` does it for every project.

## Validate after every change

Always run at least steps 1 to 3 before presenting changes.

### 1. Format SQL

```bash
just fmt                              # ruff + sqlfluff fix models, active project
just sqlfluff fix models/02_stg/knmi  # one path; runs inside dbt/dbt_example
```

The sqlfluff templater uses the `dummy` target, so linting never connects, but it does need the dbt packages.

### 2. Parse and compile

Catches syntax errors, broken `{{ ref() }}` / `{{ source() }}` references and invalid Jinja.

```bash
just dbt-all deps
just dbt parse                 # your target (ENVIRONMENT, dev by default); parse never connects
just dbt parse --target dummy  # what CI and pre-commit run
just dbt compile               # renders the SQL; needs a connection
```

Repeat with `just project=dbt_x dbt ...` for any other project you touched.

### 3. Validate definitions

```bash
just validate
```

The `dbt_example` code location re-parses the project on load, so a dbt error surfaces here too. Details: [Testing](../development/testing.md).

### 4. Build changed models (needs your `.env`)

```bash
just dbt build --select stg__knmi__climate_hourly    # run + test one model
just dbt build --select +stg__knmi__climate_hourly+  # with upstream and downstream
just dbt build                                       # seeds, models, tests, everything
```

In `dev` builds go into your personal schemas (`<SNOWFLAKE_SCHEMA>_STG`, ...) of the shared `DB_EXAMPLE_DEV`, so there is nothing to break for anyone else. Check the result with `just sf query "SELECT COUNT(1) FROM dbt_info_stg.stg__knmi__climate_hourly"`, with your own prefix instead of `dbt_info`. Materializing from the Dagster UI runs the same `dbt build` under the hood.

### 5. Full suite

```bash
just test          # pytest
just pre-commit    # all hooks: ruff, ty, dbt parse, sqlfluff, Dagster, Terraform YAML
```

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Could not find profile named 'default'` | `DBT_PROFILES_DIR` not set. Use a `just` recipe, or let `.envrc` set it. |
| Missing package or macro not found | `dbt deps` not run in that project. `just dbt-all deps`. Packages are per project. |
| Dagster location `dbt_example` fails to load | The parse on load failed. `just dbt parse` shows the real error. |
| Model builds but Dagster does not see it | The component re-parses on every code-location load. Reload the location in the UI (Deployment page) or restart `just start`. |
| Schemas come out as `_TMP_STG` instead of `_STG` in `tst`, `acc` or `prd` | The project lacks the `dispatch` block that puts `dbt_common` first, so dbt's default `<target>_<custom>` naming runs. Copy the block from `dbt_example/dbt_project.yml`. |
| Source table not found while the dlt load succeeded | `ENVIRONMENT` or `SNOWFLAKE_SCHEMA` differs between the dlt run and the dbt run; both derive the source schema from the same two variables. |
| Duplicate asset keys across code locations | Two projects build the `dbt_common` models. Disable them in all but one. |
| `int__common__holiday` fails with a package error | Anaconda terms not accepted on the account. Ask a platform administrator, or disable the model. |

## Related pages

- [dbt style guide](../conventions/dbt-style-guide.md): design, placement, tests and documentation rules
- [Adding a dbt model](../development/adding-dbt-models.md): the step-by-step workflow
- [Adding a project](../development/adding-projects.md): a second project and its code location
- [Layers in practice](../architecture/layers.md): schema-level map and the reference rule
- [Transformation](../architecture/transformation.md): the package, the project and how Dagster loads them
- [Naming](../conventions/naming.md): every naming pattern
- [Testing](../development/testing.md): dbt tests and `just validate`
- [Command reference](../reference/commands.md): the dbt passthrough recipes
