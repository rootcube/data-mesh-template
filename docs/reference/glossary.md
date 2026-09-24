---
icon: material/alphabetical
---

# Glossary

The words these docs use, in alphabetical order. Concept terms come from the platform model
(see [Concepts](../concepts/index.md)); where a term belongs to one tool, the tool is in
brackets.

Asset (Dagster)
:   Dagster's unit of data: the declaration of a table or other artifact plus the function that
    produces it. Every dlt resource, dbt model, seed and Python asset here is one. Identified by
    an asset key.

Asset key (Dagster)
:   The path-like identifier of an asset. dlt loads: `dlt/ingest/<source>/<resource>`; dbt
    models and seeds: `<project>/<path>/<name>` (`dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly`), the
    same in every environment. Equal keys in different code locations are how lineage crosses locations. See
    [Orchestration](../architecture/orchestration.md).

Code location (Dagster)
:   An independently loaded bundle of definitions, listed in `workspace.yaml` and started in
    its own subprocess. This repo has `dlt` and `dbt_example`; each dbt project adds one.
    Locations never import each other.

Component, component tree (Dagster)
:   A `defs.yaml` that declares assets from configuration instead of Python: the
    `DltLoadCollectionComponent` in each source folder, the `DbtProjectComponent` in each dbt
    location. `ComponentTree.from_module()` walks a package and builds every one it finds.

Compute
:   A warehouse profile of the platform model: `terraform/config/computes/<key>.yaml` with
    sizes and auto-suspend settings. Every project and environment pair gets one warehouse per
    compute and size, named `WH_<PROJECT>_<ENV>` for the `default` compute (no suffix) and
    `WH_<PROJECT>_<ENV>__<COMPUTE>_<SIZE>` otherwise (`WH_EXAMPLE_DEV__TFM_S`). The starter
    ships `default` (required), `ingest` and `transform`; `analysis` and `reporting` are
    disabled. See [Compute](../concepts/compute.md).

`_conf/`
:   The folder next to a model's SQL that holds its YAML (description, columns, tests), with
    the same file stem. Never put YAML next to the SQL.

Dataset (dlt)
:   The schema a pipeline loads into. Here `source_dataset()` in
    `dlt_pipelines/utils/destination.py`: the source layer, `_SRC` or `<SNOWFLAKE_SCHEMA>_SRC`
    in `dev`.

`DAGSTER_HOME`
:   Where the Dagster instance keeps run history and event logs. Here `.dagster/` inside the
    repo, set by the justfile and `.envrc`; `dagster.yaml` in it is the instance config.

Dispatch (dbt)
:   The order in which dbt looks up macro overrides. `search_order: ["dbt_common", "dbt"]` in a
    project's `dbt_project.yml` makes `dbt_common`'s `generate_schema_name` and
    `set_query_tag` win over dbt's defaults.

`dbt_common`
:   The shared dbt package under `dbt/dbt_common/`: macros (schema naming, query tag, run
    logging, run-metadata upload), generic tests, seeds and the generic calendar, time and
    environment dimensions. Installed by every project as a local package; built by exactly one
    (`dbt_example`). Not runnable on its own.

`dbt_example`
:   The dbt project of the `example` project, under `dbt/dbt_example/`, and the Dagster code
    location of the same name. Home of the KNMI source and staging model.

`dbt_utils`
:   The dbt-labs package of generic macros and tests, installed by every project's
    `packages.yml`.

`defs.yaml`
:   See *component*.

Dummy target (dbt)
:   The `dummy` output in `dbt/profiles.yml`: an in-memory DuckDB, so dbt can parse and
    compile and sqlfluff can lint without Snowflake credentials. Used by `just check`, the
    pre-commit hooks and CI (`DBT_TARGET=dummy`). It counts as a personal environment for
    schema naming, and the `on-run-end` metadata upload skips it.

Engineer
:   One of the two personas. Works in the repository: dlt loads, dbt models, Python assets,
    Dagster. Holds `RL_<PROJECT>_DEV__ENG` and works in personal schemas of the development
    database. Never runs Terraform.

Environment
:   A stage a project exists in: `terraform/config/environments/<key>.yaml` with a short
    `code`. Five ship: development (`dev`, required), test (`tst`), acceptance (`acc`),
    production (`prd`, required) and sandbox (`sbx`); test and sandbox are `disabled: true` in
    the starter. The `example` project deploys to development and production. `ENVIRONMENT` in
    `.env` selects the one a checkout runs as. See [Environment](../concepts/environment.md).

Full refresh (dlt)
:   `just dlt run <source> --full-refresh`: drop the source's tables and state in the
    destination, then load. Maps to `pipeline.run(source, refresh="drop_sources")`.

Group (Dagster)
:   How the asset catalog is organized. dlt loads: `dlt/ingest/<source>`; dbt nodes: their
    key without its last segment (`dbt_example/models/02_stg/knmi`), which nests them by
    project, package, layer and domain.

Hooks (dbt)
:   SQL or macro calls that run around an invocation. `on-run-start` in `dbt_example` prints
    the run-info banner; `on-run-end` in `dbt_common` uploads run metadata to the metadata
    layer and prints the summary, in every project that installs the package.

Job (Dagster)
:   A named asset selection you can launch as one run. `job_dlt_ingest_all` (every
    `dlt/ingest` asset) and `job_dbt_example_build_all` (the whole project).

`just`
:   The task runner. Every command in these docs is a recipe in the `justfile`; run bare `just`
    to list them. `just project=dbt_x dbt ...` targets another dbt project.

Key and code (configuration)
:   Every YAML file under `terraform/config/` is addressed by its file name, the *key*
    (`development`, `staging`, `engineer`), and carries a short *code* used in Snowflake names
    (`dev`, `stg`, `eng`). Projects, users and role privileges reference keys; the generated
    names use codes.

Key pair
:   RSA key pair for Snowflake authentication. `just sf setup` generates it under
    `~/.snowflake/keys/`, registers the public key on your user and writes the private key
    path to `.env`. No passwords in files. `just sf keygen <name>` makes one for a
    service user.

KNMI
:   Koninklijk Nederlands Meteorologisch Instituut, the Dutch weather service. Its free hourly
    observations endpoint is the starter source.

Layer
:   A stage of the data flow inside a project, `terraform/config/layers/<key>.yaml`, and one
    schema per layer in every project database. The `example` project uses source (`_SRC`),
    reference (`_REF`), staging (`_STG`), integration (`_INT`), mart (`_MRT`), expose (`_EXP`),
    metadata (`_MTD`) and temporary (`_TMP`); import and preparation exist but are unused,
    application is disabled. See [Layer](../concepts/layer.md) and
    [Layers in practice](../architecture/layers.md).

Layer schema
:   The schema a layer lives in. In `tst`, `acc` and `prd` the provisioned `_<LAYER>` schema
    (`_STG`); in `dev` the engineer's personal schema `<SNOWFLAKE_SCHEMA>_<LAYER>`
    (`DBT_INFO_STG`). Implemented by `SnowflakeSettings.schema_for_layer()` and
    `dbt_common.generate_schema_name`; dbt source YAML repeats the rule with `env_var`.

Load package, `_dlt_load_id` (dlt)
:   One run of a pipeline produces one load package; its id is written to every row as
    `_dlt_load_id`, next to the row id `_dlt_id`.

Manifest (dbt)
:   `target/manifest.json`, the parsed graph of a project. The dbt code location produces it
    with `dbt parse --quiet` on every load and turns its nodes into assets.

Materialize (Dagster)
:   Run the function behind an asset. The **Materialize** button in the UI; for a dlt asset it
    runs the pipeline, for a dbt asset `dbt build` for the selection.

Materialization (dbt)
:   How a model is stored: `table` or `view` here, set per layer in `dbt_project.yml`.

Metadata layer, `_MTD`
:   Where the tooling writes run metadata. `dbt_common`'s `on-run-end` hook creates the
    `pre__dbt__*` tables there on first use (`pre__dbt__invocation`, `pre__dbt__model`,
    `pre__dbt__model_execution`, `pre__dbt__test_execution`, ...) and appends one row per node
    and execution per invocation.

Organisation
:   The top of the platform model and the governance boundary:
    `terraform/config/organisations/<key>.yaml` with a `code`, `name` and `desc`. The starter
    ships `example`. Teams belong to an organisation. See
    [Organisation](../concepts/organisation.md).

Package (dbt)
:   A dbt project installed into another with `dbt deps` (`packages.yml`). Here the local
    `../dbt_common` and `dbt-labs/dbt_utils`, installed into `packages/` in each project.

Personal schema
:   An engineer's private copy of a layer schema in the development database:
    `<SNOWFLAKE_SCHEMA>_<LAYER>`, for example `DBT_INFO_SRC` and `DBT_INFO_STG`. Created on
    demand by dlt and dbt; possible because the engineer role holds `CREATE SCHEMA` on
    `DB_<PROJECT>_DEV`. Lets several engineers share one development database.

Pipeline (dlt)
:   The runner object: a name (`ingest_knmi`), a destination and a dataset. `pipeline.run(source)`
    extracts, normalizes and loads. Module-level `pipeline` in `pipelines.py` is the contract.

Platform administrator
:   The other persona. Owns the Snowflake account: runs `init.sql` once, maintains the YAML
    under `terraform/config/`, applies it with Terraform, onboards people and service users.
    See [Administration](../administration/index.md).

Primary key (dlt)
:   The columns that identify a row for `merge`. `climate_hourly` uses
    `station_code, date, hour`.

Profile, target (dbt)
:   `dbt/profiles.yml` holds one profile, `default`, with the targets `dev`, `tst`, `acc`,
    `prd` (Snowflake, key pair from `.env`) and `dummy` (DuckDB, never connects). The target
    follows `ENVIRONMENT` unless `DBT_TARGET` overrides it; `DBT_PROFILES_DIR` points at `dbt/`.

Project
:   A long-lived ownership boundary in the mesh, owned by one team:
    `terraform/config/projects/<key>.yaml` with `team`, `code`, `environments`, `layers`,
    `computes` and `roles`. Each project and environment pair becomes a database
    `DB_<PROJECT>_<ENV>`; in the repo a project is one dbt project and one Dagster code
    location. The starter ships `example`. See [Project](../concepts/project.md) and
    [Adding a project](../development/adding-projects.md).

Provisioning objects
:   What `terraform/modules/snowflake/init.sql` creates once as `ACCOUNTADMIN`: the service
    user `TERRAFORM_USER` (key pair only), the role `RL_PLATFORM_PROVISIONING`, the warehouse
    `WH_PLATFORM_PROVISIONING`, the database `DB_PLATFORM_PROVISIONING` and the resource
    monitor `RM_PLATFORM_PROVISIONING`. Terraform runs as that user and role.

Purpose
:   The role code that ends a role name: `ENG` (engineer), `ANL` (analyst), `ING` (ingest),
    `TFM` (transform). `RL_<PROJECT>_<ENV>__<PURPOSE>`.

Required, disabled (configuration)
:   Two flags on environments, layers, computes and roles. `required: true` items are added to
    every project whether listed or not; `disabled: true` items are ignored everywhere, even
    when a project lists them. `just tf-validate-config` rejects an item that is both.

Resource (Dagster)
:   A configured object injected into assets by parameter name. This repo has none yet: Python
    assets open a connection with `SnowflakeSettings.from_env().connect()` instead.

Resource (dlt)
:   A function decorated with `@dlt.resource` that yields the rows of one table
    (`climate_hourly`, written as `knmi__climate_hourly`). Its name is the last segment of the
    asset key.

Role
:   A set of grants per project and environment: `terraform/config/roles/<key>.yaml` with
    privileges per compute, database and layer, and roles it inherits. Becomes the account
    role `RL_<PROJECT>_<ENV>__<PURPOSE>`. Person roles: engineer (required), analyst; system
    roles: ingest (required, dlt), transform (required, dbt). Reporting exists but is unused
    in the starter, operator and the global roles are disabled. See [Role](../concepts/role.md).

Seed (dbt)
:   A CSV under `seeds/` that dbt loads as a table into the reference layer (`seed_month`,
    `seed_unknown`, ...). Always read through its typed `stg__seed__<name>` model.

Service user
:   A Snowflake user of `TYPE = SERVICE`, key pair only, for tooling: `TERRAFORM_USER` for
    provisioning, and the users deployed environments run dlt and dbt as (holding `__ING` or
    `__TFM`). Created by hand, granted roles through `terraform/config/users/`; see
    [Onboarding](../administration/onboarding.md).

`SnowflakeSettings`
:   The dataclass in `src/orchestrator/resources/snowflake.py` that reads `SNOWFLAKE_*` and
    `ENVIRONMENT` from the environment and hands dlt, Dagster and the scripts their connection
    settings and the layer-schema rule.

Source (dbt)
:   A table dbt reads but does not build, declared in `sources/src_<source>.yml` and
    referenced with `source('knmi', 'climate_hourly')`. Carries `meta.dagster.asset_key` so
    Dagster links it to the dlt asset.

Source (dlt)
:   A function decorated with `@dlt.source` that yields resources (`knmi_source()`).
    Module-level `source` in `pipelines.py` is the contract.

Source layer, `_SRC`
:   Where dlt lands data, one table per resource named `<source>__<entity>`
    (`knmi__climate_hourly`), columns as the API returned them. dbt reads it through a
    `src_<source>.yml`.

Team
:   Owns projects: `terraform/config/teams/<key>.yaml` with `organisation`, `code`, `name`,
    `type` and `owners`. The starter ships `platform`. See [Team](../concepts/team.md).

User
:   A person or service that may assume project roles: `terraform/config/users/<name>.yaml`
    with `login`, `type`, `create` and a `roles` list of project, role and environments.
    Terraform grants the matching `RL_<PROJECT>_<ENV>__<PURPOSE>` roles to the login, and
    creates the user when `create: true`.

`uv`
:   The Python package manager. `just init` installs it; every command runs through `uv run`
    against `.venv/`, so nothing is activated by hand.

Warehouse (Snowflake)
:   The compute a session uses. Provisioned per compute, see *Compute*; `WH_EXAMPLE_DEV` is the
    starter's development warehouse, X-Small, auto-suspends after 60 seconds.

Wildcard `*`
:   In a project file, `environments: "*"`, `layers: "*"`, `computes: "*"` or `roles: "*"`
    means every enabled item; in a user's role entry, `environments: "*"` means every
    environment of that project.

`workspace.yaml`
:   The authoritative list of Dagster code locations. `just start` and `just validate` both
    read it.

Write disposition (dlt)
:   What a load does to existing rows: `merge` (upsert on the primary key, the default here),
    `replace` (rewrite the table) or `append`.
