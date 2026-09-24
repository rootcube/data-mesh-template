---
icon: material/database-cog
---

# Transformation (dbt)

All transformation is dbt on Snowflake. Under `dbt/` you find one shared `profiles.yml`, a
package called `dbt_common` and one project called `dbt_example`. The layout is built for more:
every Project of the mesh gets its own dbt project next to `dbt_example`, all installing the
same `dbt_common`. Style and naming live in the [dbt style guide](../conventions/dbt-style-guide.md);
this page covers the structure.

```
dbt/
├── profiles.yml              # profile `default`: targets dev, prd + dummy; DBT_PROFILES_DIR points here
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
adapter connection to populate dbt's relation cache. The `on-run-end` metadata upload checks
for it and skips itself.

## dbt_common: the shared package

`dbt_common` is installed by every project as a local package:

```yaml title="dbt/dbt_example/packages.yml"
packages:
  - local: ../dbt_common

  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
```

`dbt_common` itself declares no packages (`packages: []`); a consuming project lists `dbt_utils`
and anything else it needs directly. Packages install into `packages/` in each project
(`packages-install-path`), git-ignored. `just init` runs `dbt deps` everywhere through
`scripts/dbt_all.py`; after a change to `packages.yml`, run `just dbt-all deps`.

It contributes four things.

### Macros

| Macro | What it does |
|-------|--------------|
| `generate_schema_name` | The platform's schema rule: `_<LAYER>` in shared environments, `<target.schema>_<LAYER>` in `dev` (and `dummy`); no `+schema` means `target.schema`. Overrides dbt's default |
| `set_query_tag` | Tags every Snowflake query with `dbt_invocation_id:<id>`, so a run is one filter in the query history |
| `log_run_info` | The banner at the start of a run: invocation id, target, organization, account, database, warehouse, threads, user, plus Snowsight links to the catalog and the query history |
| `log_run_summary` | The summary at the end: models, tests and seeds by status, failed and warned tests, failed models, the five slowest models, total runtime |
| `upload_results` and `macros/dbt_artifacts/` | The run-metadata upload into the metadata layer (vendored from `dbt_artifacts` v2.10.0, Snowflake only, self-creating tables) |
| `utc_now`, `utc_today` | `SYSDATE()`-based timestamps that ignore the session timezone |
| `search_optimization`, `format_duration`, `terminal_colors` | Helpers: a post-hook that adds search optimization to a table, `HH:MM:SS` formatting, ANSI colours for the run banners (off unless the dbt var `terminal_colors` is `true`) |

The first two override dbt's own macros. That only works when the consuming project puts
`dbt_common` before `dbt` in its dispatch order:

```yaml title="dbt/dbt_example/dbt_project.yml (excerpt)"
dispatch:
  - macro_namespace: dbt
    search_order: ["dbt_common", "dbt"]
```

Forget that block in a new project and dbt falls back to its own `generate_schema_name`, which
yields `<target.schema>_<custom>` in every environment: right by accident in `dev`, but
`_TMP_STG` instead of `_STG` in the shared environments.

### Generic tests

Four tests under `dbt/dbt_common/tests/generic/`, called as `dbt_common.<test>` from a
model's `_conf/` YAML:

| Test | Level | Passes when |
|------|-------|-------------|
| `has_data` | model | The model has at least one row (`store_failures` is off for this one) |
| `rows_expected` | model | `COUNT(*)` equals the given `value` |
| `not_empty` | column | No row has an empty string (or `NULL`) in the column |
| `not_negative` | column | No value is below zero |

`stg__knmi__climate_hourly` uses `has_data` and `not_negative` next to dbt's `not_null` and
`dbt_utils.unique_combination_of_columns`.

### Seeds and common models

Four seeds (`seed_environment`, `seed_month`, `seed_weekday`, `seed_unknown`), their typed
`stg__seed__*` models, the `int__common__*` chain and three dimensions
(`dim__common__calendar`, `dim__common__time`, `dim__common__environment`). The whole chain
is drawn on [Layers in practice](layers.md#the-common-dimensions-from-dbt_common). Each project
that installs `dbt_common` builds its own copy; in Dagster they show up under the group
`dbt_common`.

!!! warning "Exactly one project builds them"
    Two projects building `dbt_common` models produce the same asset keys in two code
    locations, which Dagster rejects. `dbt_example` builds them (`dbt_common: +enabled: true`
    in its `dbt_project.yml`). Every other project disables them and, if it needs a shared
    dimension, reads it as a source. See [Adding a project](../development/adding-projects.md).

`int__common__holiday` is a Python model that runs as Snowpark inside Snowflake and imports
the `holidays` package from the Anaconda channel; the country comes from the `holiday_country`
var (`NL` by default) in the project's `dbt_project.yml`. An administrator accepts the Anaconda
terms once per account, or you disable the model
([Snowflake provisioning](../administration/snowflake-provisioning.md)).

### The hooks and the metadata layer

Two hooks bracket every run. `dbt_example` opens with the run-info banner:

```yaml title="dbt/dbt_example/dbt_project.yml (excerpt)"
on-run-start:
  - "{{ dbt_common.log_run_info() }}"
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
it writes to `_MTD` in the shared environments and to `<PREFIX>_MTD` in `dev`. It first creates
that schema (in `dev`) and the `pre__dbt__*` tables if they do not exist, then inserts one row
per model, test, seed, execution and so on for this invocation. On `dbt source freshness`
runs it uploads only the freshness results and the invocation, not the graph. Nothing else has
to run first, and a monitoring project could later read those tables as sources.

## dbt_example: the first project

`dbt_project.yml` says what a project looks like:

- `model-paths: ["models", "sources"]`: models per layer folder, source YAML in `sources/`.
- The layer block: `02_stg`, `03_int` and `04_mrt` as `table`, `05_exp` as `view`, each with its
  `+schema` (`stg`, `int`, `mrt`, `exp`) and `layer=<name>` tag. Seeds go to `ref`.
- `data_tests: +store_failures: true` with `+schema: tmp`.
- `dbt_common: +enabled: true`.
- The dispatch block and the `on-run-start` hook shown above.

Today it holds one source (`src_knmi.yml`) and one model (`stg__knmi__climate_hourly`). The
`03_int`, `04_mrt` and `05_exp` folders are empty and waiting; dbt warns about their unused
config paths until the first model lands there.

Run it from the project folder, which is what `just dbt` does:

```bash
just dbt build                                   # seed, run, test, in dependency order
just dbt build --select stg__knmi__climate_hourly+
just dbt parse --target dummy                    # no connection
just project=dbt_other dbt build                 # another project under dbt/
just dbt-all parse --target dummy                # every project
```

## How Dagster loads a project

Each dbt project is one Dagster code location. The location's `defs/dbt/defs.yaml` declares a
`DbtProjectComponent` with the project and profiles directories; `prepare_project_cli_args:
["parse", "--quiet"]` re-parses the project on every code-location load, so the asset graph
always matches the models on disk. Model asset keys follow the file path
(`dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly`, the same in every environment); sources take
their key from `config.meta.dagster.asset_key`; the group is the key without its last segment
(`dbt_example/models/02_stg/knmi`). Details on
[Orchestration](orchestration.md#the-dbt-locations).

## One project per mesh node

The point of the layout is that adding a Project is copying a folder, not redesigning
anything: `dbt/dbt_<project>` with its own `dbt_project.yml`, the same `packages.yml`, a matching
Dagster location, and a `terraform/config/projects/<project>.yaml` for its database.
`scripts/dbt_all.py` picks the new project up automatically, so `just init`, the pre-commit
parse hook and CI cover it from the first commit. The steps are on
[Adding a project](../development/adding-projects.md).

## Related pages

- [Layers in practice](layers.md): the schemas and the reference rule
- [Adding a dbt model](../development/adding-dbt-models.md): a new model, its `_conf` YAML and tests
- [SQL style](../conventions/sql-style.md): what sqlfluff enforces
