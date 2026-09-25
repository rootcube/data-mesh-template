---
icon: material/tag-text
---

# Naming

Every name in this repo (dbt model, column, dlt table, Dagster job, Snowflake object, Terraform
config file) follows a pattern. This page is the consolidated reference. Nothing checks these
names automatically except the Terraform YAML schemas; reviewers and the patterns below do the
rest.

## Ground rules

- **`snake_case`** everywhere; no quoted identifiers.
- **Singular** (`station`, not `stations`): models sort and group better, and plural adds nothing.
- **English**, with abbreviations only when commonly known.
- Avoid reserved words (`SELECT`, `VALUE`, `DATE`) as identifiers for your own columns.
- Name things **once**; do not rename the same concept as it moves through layers.

## The mesh

The platform model is Organisation > Team > Project > Environment > Layer, and every Snowflake
name is built from the same short codes:

| Concept | Code | Examples |
|---|---|---|
| Project | lowercase, 2 to 20 characters (`terraform/config/projects/<project>.yaml`, `code`) | `example`, `energy` |
| Environment | `dev`, `tst`, `acc`, `prd` | `.env` `ENVIRONMENT=dev` |
| Layer | `src`, `ref`, `stg`, `int`, `mrt`, `exp`, `mtd`, `tmp` | `+schema: stg` |
| Role purpose | `eng` engineer, `anl` analyst, `ing` ingest, `tfm` transform | `RL_EXAMPLE_DEV__ENG` |

Uppercased in Snowflake object names, lowercase everywhere in the repo.

## dbt models

| Layer | Pattern | Example |
|---|---|---|
| Staging | `stg__<source>__<entity>` | `stg__knmi__climate_hourly` |
| Staging (seed) | `stg__seed__<name>` | `stg__seed__unknown` |
| Intermediate | `int__<domain>__<entity>` | `int__common__calendar` |
| Mart dimension | `dim__<domain>__<entity>` | `dim__common__calendar` |
| Mart fact | `fct__<domain>__<entity>` | `fct__weather__knmi_measurement` |
| Mart bridge | `brg__<domain>__<entity>` | `brg__weather__station_region` |
| Mart aggregate | `agg__<domain>__<entity>` | `agg__weather__station_daily` |
| Expose | `exp__<domain>__<entity>` | `exp__weather__station_weather` |
| Sources | `src_<source>.yml` | `src_knmi.yml` |
| Seeds | `seed_<name>` | `seed_unknown` |
| Exposures | `exposures/<consumer>.yml`, exposure named `<consumer>` | `weather_dashboard` |

Double underscores (`__`) separate the structural segments (layer, source or domain, entity);
single underscores separate words within a segment. In staging, `<source>` is the dlt source
folder name (`knmi`). From integration up, `<domain>` is a business domain (`common` for the
shared calendar and time models, `weather` for the KNMI chain in `dbt_example`). The `brg__` and
`agg__` examples are illustrative; `dbt_example` ships `dim__weather__knmi_station`,
`dim__weather__knmi_measurement_type`, `fct__weather__knmi_measurement` and `exp__weather__station_weather`.

The model name is also the last segment of its Dagster asset key and its Snowflake table or view
name, so pick it once and carefully. The asset key carries the project name
(`<project>/models/...`), so a model name only has to be unique within its project; distinct
names across the repo keep the catalog searchable.

### Columns

| Type | Pattern | Example |
|---|---|---|
| Surrogate key (dim) | `id_dim__<domain>__<entity>` | `id_dim__common__calendar` |
| Surrogate key (fct) | `id_fct__<domain>__<entity>` | `id_fct__weather__knmi_measurement` |
| Foreign key to a dimension | `id_dim__<domain>__<entity>` | `id_dim__common__calendar` |
| Role-played foreign key (same dim twice) | `id_dim__<domain>__<entity>__<role>` | `id_dim__common__calendar__observed` |
| Column in a role or context | `<column>__<context>` | `station_code__nearest` |
| Boolean | `is_` / `has_` prefix | `is_holiday`, `is_weekend` |
| Timestamp | `<event>_at` | `observed_at` |
| Date | `<event>_date` | `first_date_of_month` |
| Measure with a unit | `<measure>_<unit>` | `temperature_celsius`, `wind_speed_ms`, `precipitation_mm`, `relative_humidity_pct` |
| Code, name, description | `<entity>_code`, `<entity>_name`, `<entity>_desc` | `month_code`, `month_name`, `unknown_desc` |
| dlt bookkeeping | `_dlt_<name>` | `_dlt_load_id` |
| CTE | `cte_<description>` | `cte_source`, `cte_calendar` |

### Tests

Every test is named, so a failure reads as a sentence in the terminal and in `_TMP`:

- Model-level: `<model_name>__<test_type>`, e.g. `stg__knmi__climate_hourly__has_data`; for a
  composite uniqueness test the columns go in between:
  `stg__knmi__climate_hourly__station_code__observed_at__unique`.
- Column-level: `<model_name>__<column_name>__<test_type>`, e.g.
  `stg__knmi__climate_hourly__station_code__not_null`,
  `dim__common__calendar__id_dim__common__calendar__unique`.

### Tags

Tags are `key=value` strings. The layer tag (`layer=stg`, `layer=int`, `layer=mrt`, `layer=exp`)
is set per folder in `dbt_project.yml`. The shared models add `owner=`, `system=` and `category=`
in their `config()`; use the same keys if you tag.

## dlt

One folder per source under `dlt_pipelines/pipelines/ingest/<source>/`, with `constants.py`,
`source.py`, `pipelines.py` and `defs.yaml`. Everything else derives from the folder and the names
in `pipelines.py`:

| Property | Pattern | KNMI |
|---|---|---|
| Source folder | `<source>` (what `just dlt run <source>` takes) | `knmi` |
| dlt source name | `<source>__<entity>` | `knmi__climate_hourly` |
| dlt resource name | `<entity>` | `climate_hourly` |
| Snowflake table (`table_name`) | `<source>__<entity>` | `knmi__climate_hourly` |
| Pipeline name | `ingest_<source>` | `ingest_knmi` |
| Dataset (Snowflake schema) | `_SRC`, or `<SNOWFLAKE_SCHEMA>_SRC` in dev (`source_dataset()`) | `DBT_USERNAME_SRC` |
| Dagster asset key | `dlt/ingest/<source>/<entity>` | `dlt/ingest/knmi/climate_hourly` |
| Dagster group | `dlt/ingest/<source>` | `dlt/ingest/knmi` |
| Kind tags | `dlt`, `snowflake` | same |

Every source of a project shares one `_SRC` schema, which is why the table carries the source
prefix while the resource (and asset key segment) stays the bare entity. The asset key comes from
`defs.yaml` (`key_prefix: ["dlt", "ingest", "<source>"]`, `key` = the resource name). The dbt
source declares the same key under `config.meta.dagster.asset_key` and the table under
`identifier`, which is how dbt models get lineage to their upstream load. See
[ingestion](../architecture/ingestion.md) and
[adding dlt loads](../development/adding-dlt-loads.md).

## Dagster

| Kind | Pattern | Example |
|---|---|---|
| Code location (dlt) | `dlt` | `dlt` |
| Code location (dbt) | `dbt_<project>` | `dbt_example` |
| Python module of a dbt location | `orchestrator.locations.dbt.dbt_<project>.definitions` | `orchestrator.locations.dbt.dbt_example.definitions` |
| Job (dlt) | `job_dlt_ingest_all` | same |
| Job (dbt) | `job_<project>_build_all` | `job_dbt_example_build_all` |
| Asset key (dbt model) | `<project>/models/<layer folder>/<domain>/<name>`; nodes from a package get `<project>/packages/<package>/...` | `dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly`, `dbt_example/packages/dbt_common/models/04_mrt/common/dim__common__calendar` |
| Asset key (dbt seed) | `<project>/seeds/<name>`, or `<project>/packages/<package>/seeds/<name>` | `dbt_example/packages/dbt_common/seeds/seed_month` |
| Asset group (dbt) | the key without its last segment | `dbt_example/models/02_stg/knmi` |
| Asset key (dbt source) | `config.meta.dagster.asset_key` from the source YAML | `dlt/ingest/knmi/climate_hourly` |
| Asset group (dbt) | the dbt package name | `dbt_example`, `dbt_common` |

`workspace.yaml` is the authoritative list of code locations; location names and module paths
both use underscores. Asset keys are the same in every environment (they never carry the
personal prefix or the `_` of a provisioned schema), which is what lets lineage cross code
locations. When you add named definitions beyond these, prefix them by kind so they are
unambiguous in the UI and CLI: `job_`, `schedule_`, `sensor_`, `check_`, `op_`. When the same
factory produces a definition per location (as `build_dbt_defs` does), embed the project in the
name (`job_dbt_example_build_all`).

## Snowflake

Provisioned by Terraform from `terraform/config` (administrators), one set per project and
environment:

| Object | Pattern | Example |
|---|---|---|
| Database | `DB_<PROJECT>_<ENV>` | `DB_EXAMPLE_DEV`, `DB_EXAMPLE_PRD` |
| Layer schema | `_<LAYER>` | `_SRC`, `_STG`, `_MRT` |
| Personal layer schema (dev only) | `<SNOWFLAKE_SCHEMA>_<LAYER>`, prefix `DBT_<USERNAME>` or the user file's `schema_prefix` | `DBT_USERNAME_STG` |
| Role | `RL_<PROJECT>_<ENV>__<PURPOSE>` | `RL_EXAMPLE_DEV__ENG`, `RL_EXAMPLE_PRD__TFM` |
| Warehouse | `WH_<PROJECT>_<ENV>[__<COMPUTE>_<SIZE>]` (the `default` compute has no suffix) | `WH_EXAMPLE_DEV` |
| Source layer stage | `ST_DEFAULT`, the default internal stage of each source-layer schema (`_SRC`, and `<SNOWFLAKE_SCHEMA>_SRC` in dev); dlt loads through it | `DB_EXAMPLE_DEV._SRC.ST_DEFAULT`, `DB_EXAMPLE_DEV.DBT_USERNAME_SRC.ST_DEFAULT` |
| dlt load files | `<stage>/dlt/ingest/<source>/<pipeline>__<load id>/<source>__<entity>.<file id>.<retry>.jsonl`, the pipeline being `ingest_<source>` | `_SRC.ST_DEFAULT/dlt/ingest/knmi/`, `DBT_USERNAME_SRC.ST_DEFAULT/dlt/ingest/knmi/` |
| Provisioning (bootstrap) | `TERRAFORM_USER`, `WH_PLATFORM_PROVISIONING`, `DB_PLATFORM_PROVISIONING` | same |

An engineer's `.env` holds the dev triple of one project (`SNOWFLAKE_DATABASE=DB_EXAMPLE_DEV`,
`SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG`, `SNOWFLAKE_WAREHOUSE=WH_EXAMPLE_DEV`) and the personal
prefix `SNOWFLAKE_SCHEMA=DBT_<USERNAME>`. `just sf setup` proposes `DBT_` plus the first part
of your login, or the `schema_prefix` of your user file: the prefix Terraform provisioned your
schemas with.

Schemas inside a project database:

| Schema | Written by | Contents |
|---|---|---|
| `_SRC` | dlt | Source tables, `<source>__<entity>` (`knmi__climate_hourly`) |
| `_REF` | dbt seeds | Reference data |
| `_STG`, `_INT`, `_MRT`, `_EXP` | dbt models | The four dbt layers |
| `_TMP` | dbt tests | Stored test failures; also dbt's default schema in `tst`, `acc` and `prd` |
| `_MTD` | `dbt_common` on-run-end hook | Run metadata (`pre__dbt__*`) |

In `dev` the same set exists per engineer under the personal prefix (`DBT_USERNAME_SRC`,
`DBT_USERNAME_STG`, ...), provisioned by Terraform per engineer; a model without `+schema` would
land in the prefix itself (`DBT_USERNAME`), which is not provisioned.
`SnowflakeSettings.schema_for_layer()` and `dbt_common.generate_schema_name` implement the rule;
source YAML repeats it with `env_var`.

Snowflake folds unquoted identifiers to uppercase, so `knmi__climate_hourly` and
`KNMI__CLIMATE_HOURLY` are the same table. The connection settings are the `SNOWFLAKE_*`
variables in `.env`; see [environment variables](../reference/environment-variables.md) and
[Snowflake](../architecture/snowflake.md).

## Terraform configuration

One YAML file per object under `terraform/config/`, validated by `just tf-validate-config`
against `terraform/config/_validation/schemas/`. Files refer to each other by file name (key),
not by code:

| Folder | File name | Refers to |
|---|---|---|
| `projects/` | `<project>.yaml` (`code` inside matches) | `team`, `environments`, `layers`, `computes`, `roles` by key |
| `users/` | `<name>.yaml`, one per person or service | `roles[].project` and `roles[].role` by key |
| `teams/` | `<team>.yaml` | `organisation` by key |
| `environments/` | `development`, `test`, `acceptance`, `production` | `code`: `dev`, `tst`, `acc`, `prd` |
| `layers/` | `source`, `reference`, `staging`, `integration`, `mart`, `expose`, `metadata`, `temporary`, ... | `code`: `src`, `ref`, `stg`, ... |
| `roles/` | `engineer`, `analyst`, `ingest`, `transform`, ... | `code`: `eng`, `anl`, `ing`, `tfm` |
| `computes/` | `default`, `ingest`, `transform`, ... | `code`: empty for `default`, `ing`, `tfm` |

## Python and tests

Python naming (constants, classes, functions, booleans) is covered in
[Python style](python-style.md#naming). Test files are `tests/test_<module>.py`, test functions
`test_<function>_<what_it_should_do>`; see [Testing](../development/testing.md).
