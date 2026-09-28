---
icon: material/database-cog
---

# Transformation (dbt)

All transformation is dbt on Snowflake. Under `dbt/` you find one shared `profiles.yml`, a
package called `dbt_common` and one project called `dbt_example`. The layout is built for more:
every Project of the mesh gets its own dbt project next to `dbt_example`, all installing the
same `dbt_common`. How the models themselves are written is the
[dbt style guide](../reference/dbt-style-guide.md); this page is the structure around them.

```
dbt/
├── profiles.yml              # profile `default`: targets dev, tst, acc, prd + dummy; DBT_PROFILES_DIR points here
├── .sqlfluff                 # shared lint config: dbt templater with the dummy target
├── dbt_common/               # package: macros, generic tests, seeds, generic models. Not runnable on its own
│   ├── dbt_project.yml       #   layer config for its own models + the on-run-end hooks
│   ├── macros/               #   generate_schema_name, set_query_tag, log_run_*, dbt_artifacts/, ...
│   ├── tests/generic/        #   has_data, rows_expected, not_empty, not_negative
│   ├── seeds/                #   seed_environment, seed_month, seed_weekday, seed_unknown
│   └── models/               #   02_stg/seed, 03_int/common, 04_mrt/common
└── dbt_example/              # project: the first mesh node
    ├── dbt_project.yml       #   dispatch order, layers, hooks
    ├── packages.yml          #   local ../dbt_common + dbt_utils
    ├── sources/src_knmi.yml  #   the source-layer tables dlt landed
    ├── models/02_stg 03_int 04_mrt 05_exp
    └── seeds/ macros/ tests/
```

## One profile, one target per environment

Every project uses the `default` profile from `dbt/profiles.yml`. `DBT_PROFILES_DIR` points at
`dbt/` (set by the justfile, `.envrc` and CI), so `just dbt ...` and a bare `dbt` in the project
folder resolve the same file. The target follows `ENVIRONMENT` from `.env`; `DBT_TARGET`
overrides it:

```yaml title="dbt/profiles.yml (excerpt)"
default:
  target: "{{ env_var('DBT_TARGET', env_var('ENVIRONMENT', 'dev')) }}"
```

| Target | Connects as | Schemas | Threads | Use |
|--------|-------------|---------|---------|-----|
| `dev` | Your user with the key pair from `.env` (`SNOWFLAKE_*` through `env_var()`) | Personal, `<SNOWFLAKE_SCHEMA>_<LAYER>` in `DB_<PROJECT>_DEV` | 8 | Every local run |
| `tst`, `acc`, `prd` | The same variables, filled with the transform system user's key pair and `RL_<PROJECT>_<ENV>__TFM` | The provisioned `_<LAYER>` schemas of `DB_<PROJECT>_<ENV>` | 16 | Deployed runs |
| `dummy` | An in-memory DuckDB (`dbt-duckdb`), never Snowflake. SQL is rendered, not executed | n/a | 1 | `dbt parse` in CI and pre-commit, sqlfluff's dbt templater |

Every Snowflake target reads exactly the same variable names, so switching environment is a
different `.env`, not a different profile. The `dummy` target is what lets `just check`, the
pre-commit hooks and a fresh CI runner parse every project without a Snowflake account. It is
DuckDB rather than fake Snowflake values because sqlfluff's dbt templater needs a working
adapter connection to populate dbt's relation cache. The metadata upload checks for it and
skips itself, and `macros/dbt_artifacts/database_specific_helpers/default_fallbacks.sql`
provides `default__` variants of the Snowflake-only macros so dispatch still resolves on DuckDB.

## dbt_common: the shared package

`dbt_common` is installed by every project as a local package:

```yaml title="dbt/dbt_example/packages.yml"
--8<-- "dbt/dbt_example/packages.yml"
```

It declares no packages of its own (`packages: []`); a consuming project lists `dbt_utils` and
anything else it needs directly. Packages install into a git-ignored `packages/` in each project
(`packages-install-path`). `just init` runs `dbt deps` everywhere through `scripts/dbt_all.py`;
after a change to `packages.yml`, run `just dbt-all deps`.

It contributes four things: macros, generic tests, seeds and the common models.

### Macros

| Macro | What it does |
|-------|--------------|
| `generate_schema_name` | The platform's schema rule: `_<LAYER>` in shared environments, `<target.schema>_<LAYER>` in `dev` and `dummy`; no `+schema` means `target.schema`. Overrides dbt's default |
| `set_query_tag` | Tags every Snowflake query with `dbt_invocation_id:<id>`, so a run is one filter in the query history |
| `log_run_info`, `log_run_summary` | The banner at the start of a run (invocation id, target, account, database, warehouse, threads, user, plus Snowsight links to the catalog and the query history) and the summary at the end (counts by status, failed and warned tests, the five slowest models, total runtime) |
| `refresh_stages` | `ALTER STAGE <source-layer schema>.ST_DEFAULT REFRESH` at the start of `run` and `build`: the directory table of the dlt load stage, which internal stages never refresh by themselves; skipped on `dummy` |
| `upload_results` and `macros/dbt_artifacts/` | The run-metadata upload into the metadata layer (vendored from `dbt_artifacts` v2.10.0, Snowflake only, self-creating tables) |
| `utc_now`, `utc_today` | `SYSDATE()`-based timestamps that ignore the session timezone |
| `search_optimization`, `format_duration`, `terminal_colors` | Helpers: a post-hook that adds search optimization to a table (`EQUALITY(*), SUBSTRING(*)` by default, nothing for views), `HH:MM:SS` formatting, ANSI colours for the run banners (off unless the dbt var `terminal_colors` is `true`) |

The first two override dbt's own macros. That only works when the consuming project puts
`dbt_common` before `dbt` in its dispatch order:

```yaml title="dbt/dbt_example/dbt_project.yml (excerpt)"
dispatch:
  - macro_namespace: dbt
    search_order: ["dbt_common", "dbt"]
```

Forget that block in a new project and dbt falls back to its own `generate_schema_name`, which
yields `<target.schema>_<custom>` in every environment: right by accident in `dev`, and
`_TMP_STG` instead of `_STG` everywhere else.

### Generic tests

Four tests under `dbt/dbt_common/tests/generic/`, called as `dbt_common.<test>` from a model's
`_conf/` YAML: `has_data` (the model has at least one row, with `store_failures` off for this
one), `rows_expected` (`COUNT(*)` equals a given `value`), `not_empty` (no empty string or
`NULL` in a column) and `not_negative` (no value below zero).

### Seeds and common models

`dbt_common` ships four seeds, their typed `stg__seed__*` models, the `int__common__*` chain
and three dimensions. Its seeds are `+full_refresh: true`, so a seeded table always matches the
CSV it came from. The
whole chain is drawn on [Layer](layer.md#the-common-chain-from-dbt_common); each project that
installs `dbt_common` could build its own copy, but exactly one does, because two copies write
the same tables into the one database `.env` points at. `dbt_example` is that one; the opt-out
for every other project is in the
[dbt style guide](../reference/dbt-style-guide.md).

## The hooks and the metadata layer

Two hooks bracket every run. `dbt_example` opens with the run-info banner and the stage refresh:

```yaml title="dbt/dbt_example/dbt_project.yml (excerpt)"
on-run-start:
  - "{{ dbt_common.log_run_info() }}"
  - "{{ dbt_common.refresh_stages() }}"
```

`dbt_common` closes with the metadata upload and the summary. Package-level `on-run-end` hooks
execute in the parent project's runs, so every project that installs `dbt_common` gets both
without declaring anything:

```yaml title="dbt/dbt_common/dbt_project.yml (excerpt)"
on-run-end:
  - "{% if execute and flags.WHICH in ['run', 'build', 'test', 'seed', 'freshness'] and target.name | trim | lower != 'dummy' %}{{ dbt_common.upload_results(results) }}{% endif %}"
  - "{% if execute and flags.WHICH in ['run', 'build', 'test', 'seed'] %}{{ dbt_common.log_run_summary(results) }}{% endif %}"
```

`upload_results` resolves the metadata schema through `generate_schema_name('mtd', none)`, so
it lands in the provisioned `_MTD` (your personal one in `dev`). It creates the `pre__dbt__*`
tables if they do not exist, twelve of them (`invocation`, `model`, `model_execution`, `test`,
`test_execution`, `seed`, `seed_execution`, `source`, `source_freshness`, `snapshot`,
`snapshot_execution`, `exposure`), and inserts the rows of this invocation. A
`dbt source freshness` run uploads only the freshness results and the invocation, not the
graph. Nothing has to run first, and a monitoring project could read those tables as sources.

## dbt_example: the first project

`dbt_project.yml` says what a project looks like: `model-paths: ["models", "sources",
"exposures"]`, one block per layer folder with its `+schema` and `layer=<name>` tag, seeds to
`ref`, `data_tests: +store_failures: true` with `+schema: tmp`, `dbt_common: +enabled: true`,
and the dispatch and hook blocks above.

Today it holds one source (`src_knmi.yml`), two seeds (`seed_knmi_station`,
`seed_knmi_measurement_type`) and the `weather` chain from `stg__knmi__climate_hourly` through
`int__weather__knmi_measurement`, `dim__weather__knmi_station`,
`dim__weather__knmi_measurement_type` and `fct__weather__knmi_measurement` to
`exp__weather__station_weather`, whose consumer is the `weather_dashboard` exposure.

Run it from the project folder, which is what `just dbt` does:

```bash
just dbt build                                   # seed, run, test, in dependency order
just dbt build --select stg__knmi__climate_hourly+
just dbt parse --target dummy                    # no connection
just project=dbt_other dbt build                 # another project under dbt/
just dbt-all parse --target dummy                # every project
```

## One project per mesh node

The point of the layout is that adding a Project is copying a folder, not redesigning anything:
`dbt/dbt_<project>` with its own `dbt_project.yml`, the same `packages.yml`, a matching Dagster
location, and a `terraform/config/projects/<project>.yaml` for its database.
`scripts/dbt_all.py` picks the new project up automatically, so `just init`, the pre-commit
parse hook and CI cover it from the first commit. The steps are on
[Adding a project](../build/adding-projects.md).

Each dbt project is one Dagster code location, which re-parses the project on every load so the
asset graph matches the models on disk: [Orchestration](orchestration.md#the-dbt-locations).

## Related pages

- [Layer](layer.md): the schemas the models build into
- [Adding a dbt model](../build/adding-dbt-models.md): a new model, its `_conf` YAML and tests
- [SQL style](../reference/sql-style.md): what sqlfluff enforces
