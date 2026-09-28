---
icon: material/alphabetical
---

# Glossary

The words these docs use, in alphabetical order. Concept terms come from the platform model
([Understand](../understand/index.md)); where a term belongs to one tool, the tool is in
brackets. Every term carries its own anchor, to link straight at.

Access, access role { #access-role }
:   A tier of privileges on a layer: `view`, `read`, `edit` or `full`
    (`terraform/config/accesses/<tier>.yaml`, plus the layer's own extras). Every layer × tier
    becomes an account role `AR_<PROJECT>_<ENV>__<LAYER>__<ACCESS>`, inherited by the project
    roles that name it. See [Access](../understand/access.md).

Asset (Dagster) { #asset }
:   Dagster's unit of data: a table or other artifact plus the function that produces it. Every
    dlt resource, dbt model, seed and Python asset here is one.

Asset key (Dagster) { #asset-key }
:   The path-like identifier of an asset, the same in every environment:
    `dlt/ingest/<source>/<resource>` for a dlt load, `<project>/<path>/<name>` for a dbt node.
    Equal keys in different code locations are how lineage crosses them. Patterns:
    [Naming](naming.md#dagster).

Code location (Dagster) { #code-location }
:   An independently loaded bundle of definitions, listed in `workspace.yaml` and started in its
    own subprocess. The repo has `dlt` and `dbt_example`; each dbt project adds one. Locations
    never import each other.

Component, component tree (Dagster) { #component }
:   A `defs.yaml` that declares assets from configuration instead of Python: the
    `DltLoadCollectionComponent` in each source folder, the `DbtProjectComponent` in each dbt
    location. `ComponentTree.from_module()` walks a package and builds every one it finds.

Compute { #compute }
:   A warehouse profile: `terraform/config/computes/<key>.yaml` with sizes and auto-suspend
    settings. Each project × environment gets one warehouse per compute and size. See
    [Compute](../understand/compute.md).

`_conf/` { #conf }
:   The folder next to a model's SQL that holds its YAML, under the same file stem. Never put
    YAML next to the SQL. See [File placement](dbt-style-guide.md#file-placement).

`DAGSTER_HOME` { #dagster-home }
:   Where the Dagster instance keeps run history and event logs: `.dagster/` inside the repo, set
    by the justfile and `.envrc`. The `dagster.yaml` in it is the instance config.

Dataset (dlt) { #dataset }
:   The schema a pipeline loads into, built by `source_dataset()` in
    `dlt_pipelines/utils/destination.py`: the source layer of the environment you run as.

`dbt_common` { #dbt-common }
:   The shared dbt package under `dbt/dbt_common/`: macros, generic tests, seeds and the common
    calendar, time and environment dimensions. Installed by every project, built by exactly one.
    See [dbt_common](dbt-style-guide.md#dbt_common).

`dbt_example` { #dbt-example }
:   The dbt project of the `example` project (`dbt/dbt_example/`) and the Dagster code location
    of the same name. Home of the KNMI source and staging model.

`dbt_utils` { #dbt-utils }
:   The dbt-labs package of generic macros and tests, installed by every project's `packages.yml`.

`defs.yaml` { #defs-yaml }
:   See [component](#component).

Dispatch (dbt) { #dispatch }
:   The order in which dbt looks up macro overrides. `search_order: ["dbt_common", "dbt"]` in a
    project's `dbt_project.yml` makes `dbt_common`'s `generate_schema_name` and `set_query_tag`
    win over dbt's defaults.

`DUCKDB_PATH` { #duckdb-path }
:   The file behind the `local` dbt target and the local dlt destination:
    `.duckdb/data/local.duckdb`, exported by the justfile and `.envrc`. Not in `.env`. See
    [Local target](#local-target).

Engineer { #engineer }
:   One of the two personas. Works in the repository (dlt loads, dbt models, Python assets,
    Dagster), holds `RL_<PROJECT>_DEV__ENG`, works in personal schemas, never runs Terraform.

Environment { #environment }
:   A stage a project exists in: `terraform/config/environments/<key>.yaml` with a short `code`
    (`dev`, `tst`, `acc`, `prd`, `sbx`). `ENVIRONMENT` in `.env` selects the one a checkout runs
    as, or `local` (no Terraform environment, no Snowflake connection at all, see
    [Local target](#local-target)). See [Environment](../understand/environment.md).

Full refresh (dlt) { #full-refresh }
:   `just dlt run <source> --full-refresh`: drop the source's tables and state in the
    destination, then load. Maps to `pipeline.run(source, refresh="drop_sources")`.

Group (Dagster) { #group }
:   How the asset catalog is organized: `dlt/ingest/<source>` for dlt loads, the asset key
    without its last segment for dbt nodes, which nests them by project, package, layer and
    domain.

Hooks (dbt) { #hooks }
:   Macro calls that run around an invocation. `on-run-start` prints the run banner and refreshes
    the load stage; `on-run-end` uploads run metadata and prints the summary, in every project
    that installs `dbt_common`.

Job (Dagster) { #job }
:   A named asset selection you can launch as one run, `job__<location>__<name>`. Never written
    per instance; the factories derive them. See
    [Orchestration](../understand/orchestration.md).

`just` { #just }
:   The task runner. Every command in these docs is a recipe in the `justfile`; run bare `just`
    to list them. See [Commands](commands.md).

Key and code (configuration) { #key-and-code }
:   Every YAML under `terraform/config/` is addressed by its file name, the *key* (`development`,
    `staging`, `engineer`), and carries a short *code* used in Snowflake names (`dev`, `stg`,
    `eng`). Configuration references keys; generated names use codes.

Key pair { #key-pair }
:   The RSA key pair Snowflake authentication uses. `just sf setup` generates it under
    `~/.snowflake/keys/`, registers the public key on your user and writes the path to `.env`. No
    passwords in files. See [Snowflake authentication](../start/snowflake-auth.md).

KNMI { #knmi }
:   Koninklijk Nederlands Meteorologisch Instituut, the Dutch weather service. Its free hourly
    observations endpoint is the starter's one source.

Layer { #layer }
:   A stage of the data flow inside a project (`terraform/config/layers/<key>.yaml`), and one
    schema per layer in every project database: source, reference, staging, integration, mart,
    expose, metadata and temporary. See [Layer](../understand/layer.md).

Layer schema { #layer-schema }
:   The schema a layer lives in: the provisioned `_<LAYER>` outside `dev`, your personal
    `<SNOWFLAKE_SCHEMA>_<LAYER>` in `dev`. The table:
    [How the values become schema names](environment-variables.md#how-the-values-become-schema-names).

Load package, `_dlt_load_id` (dlt) { #load-package }
:   One run of a pipeline produces one load package; its id is written to every row as
    `_dlt_load_id`, next to the row id `_dlt_id`.

Local target (dbt) { #local-target }
:   The `local` output in `dbt/profiles.yml`: a DuckDB file at `DUCKDB_PATH`
    (`.duckdb/data/local.duckdb`), so dbt builds, tests, parses, compiles and sqlfluff lints
    without Snowflake credentials. Used by `ENVIRONMENT=local` checkouts and by `just check`,
    the pre-commit hooks and CI (`DBT_TARGET=local`). It counts as a personal environment for
    schema naming, and every hook that talks to Snowflake skips it.

Manifest (dbt) { #manifest }
:   `target/manifest.json`, the parsed graph of a project, whose nodes a dbt code location turns
    into assets. `dagster dev` refreshes it with `dbt parse --quiet` on every load; every other
    load reads the one the last `dbt parse` wrote.

Materialize (Dagster) { #materialize }
:   Run the function behind an asset: the **Materialize** button in the UI, which runs the
    pipeline for a dlt asset and `dbt build` for a dbt asset.

Materialization (dbt) { #materialization }
:   How a model is stored, `table` or `view` here, set per layer folder in `dbt_project.yml`.

Metadata layer, `_MTD` { #metadata-layer }
:   Where `dbt_common`'s `on-run-end` hook writes run metadata, as `pre__dbt__*` tables created
    on first use: one row per node and execution per invocation.

Organisation { #organisation }
:   The top of the platform model and the governance boundary. Teams belong to one. See
    [Organisation](../understand/organisation.md).

Package (dbt) { #package }
:   A dbt project installed into another with `dbt deps` (`packages.yml`): the local
    `../dbt_common` and `dbt-labs/dbt_utils`, both landing in the project's `packages/`.

Personal schema { #personal-schema }
:   An engineer's private copy of a layer schema in the development database
    (`DBT_USERNAME_STG`), provisioned by Terraform from the user file's `schema_prefix` or
    `DBT_<USERNAME>`. Lets several engineers share one development database.

Pipeline (dlt) { #pipeline }
:   The runner object: a name (`ingest_knmi`), a destination and a dataset. `pipeline.run(source)`
    extracts, normalizes and loads. The module-level `pipeline` in `pipelines.py` is the contract.

Platform administrator { #platform-administrator }
:   The other persona. Owns the Snowflake account: runs `init.sql` once, maintains the YAML under
    `terraform/config/`, applies it, onboards people and service users. See
    [Operate](../operate/index.md).

Primary key (dlt) { #primary-key }
:   The columns that identify a row for a `merge` load. `climate_hourly` uses
    `station_code, date, hour`.

Profile, target (dbt) { #profile-target }
:   `dbt/profiles.yml` holds one profile, `default`, with the targets `local` (a DuckDB file, no
    Snowflake) and `dev`, `tst`, `acc`, `prd` (Snowflake, key pair from `.env`). The target
    follows `ENVIRONMENT` unless `DBT_TARGET` overrides it; `DBT_PROFILES_DIR` points at `dbt/`.

Project { #project }
:   A long-lived ownership boundary in the mesh, owned by one team: one dbt project, one Dagster
    code location, and a database `DB_<PROJECT>_<ENV>` per environment. The starter ships
    `example`. See [Project](../understand/project.md).

Provisioning objects { #provisioning-objects }
:   What `terraform/modules/snowflake/init.sql` creates once as `ACCOUNTADMIN`: the service user
    `TERRAFORM_USER` (key pair only) with the system roles `SYSADMIN`, `SECURITYADMIN` and
    `USERADMIN`, and the warehouse `WH_PLATFORM_PROVISIONING`. The account parameters live next
    to it, in `account_settings.sql`.

Purpose { #purpose }
:   The role code that ends a role name: `ENG` (engineer), `ANL` (analyst), `ING` (ingest),
    `TFM` (transform), in `RL_<PROJECT>_<ENV>__<PURPOSE>`.

Required, disabled (configuration) { #required-disabled }
:   Two flags on environments, layers, computes and roles. `required: true` items are added to
    every project whether listed or not; `disabled: true` items are ignored everywhere, even when
    a project lists them. `just tf-validate-config` rejects an item that is both.

Resource (Dagster) { #resource-dagster }
:   A configured object injected into assets by parameter name. This repo has none yet: Python
    assets open a connection with `SnowflakeSettings.from_env().connect()` instead.

Resource (dlt) { #resource-dlt }
:   A function decorated with `@dlt.resource` that yields the rows of one table
    (`climate_hourly`, written as `knmi__climate_hourly`). Its name is the last segment of the
    asset key.

Role { #role }
:   A set of grants per project and environment (`terraform/config/roles/<key>.yaml`),
    provisioned as the account role `RL_<PROJECT>_<ENV>__<PURPOSE>`. Person roles: engineer
    (required), analyst. System roles: ingest (dlt), transform (dbt). See
    [Role](../understand/role.md).

Schedule (Dagster) { #schedule }
:   A cron that launches a job, `schedule__<location>__<name>`: the daily load per dlt source and
    the hourly source-freshness check per dbt project. Stopped by default in `dev`.

Seed (dbt) { #seed }
:   A CSV under `seeds/` that dbt loads as a table into the reference layer (`seed_month`,
    `seed_unknown`, ...). Always read through its typed `stg__seed__<name>` model.

Sensor (Dagster) { #sensor }
:   A function the daemon evaluates on an interval to decide whether to launch a job,
    `sensor__<location>__<name>`. Each dbt project's freshness sensor reads the `sources.json` of
    the last freshness check and rebuilds the downstream of the sources whose `max_loaded_at`
    advanced. Stopped by default in `dev`.

Service user { #service-user }
:   A Snowflake user of `TYPE = SERVICE`, key pair only, for tooling: `TERRAFORM_USER` for
    provisioning, and the users deployed environments run dlt and dbt as. See
    [Onboarding](../operate/onboarding.md).

`SnowflakeSettings` { #snowflake-settings }
:   The dataclass in `src/orchestrator/resources/snowflake.py` that reads `SNOWFLAKE_*` and
    `ENVIRONMENT`, and hands dlt, Dagster and the scripts their connection settings and the
    layer-schema rule. Nothing else reads those variables.

Source (dbt) { #source-dbt }
:   A table dbt reads but does not build, declared in `sources/src_<source>.yml` and referenced
    with `source('knmi', 'climate_hourly')`. Carries `meta.dagster.asset_key` and `freshness`.
    See [Sources](dbt-style-guide.md#sources).

Source (dlt) { #source-dlt }
:   A function decorated with `@dlt.source` that yields resources (`knmi_source()`). The
    module-level `source` in `pipelines.py` is the contract.

Source layer, `_SRC` { #source-layer }
:   Where dlt lands data, one table per resource named `<source>__<entity>`
    (`knmi__climate_hourly`), columns as the API returned them.

Team { #team }
:   Owns projects: `terraform/config/teams/<key>.yaml` with `organisation`, `code`, `name`,
    `type` and `owners`. The starter ships `platform`. See [Team](../understand/team.md).

User { #user }
:   A person or service that may assume project roles: `terraform/config/users/<name>.yaml` with
    `login`, `create` and a `roles` list of project, role and environments. Terraform grants the
    matching roles, and creates the user (with a one-time password) when `create: true`.

`uv` { #uv }
:   The Python package manager. `just init` installs it; every command runs through `uv run`
    against `.venv/`, so nothing is activated by hand.

Warehouse (Snowflake) { #warehouse }
:   The compute a session uses, provisioned per compute and size. `WH_EXAMPLE_DEV` is the
    starter's development warehouse: X-Small, auto-suspending after 60 seconds.

Wildcard `*` { #wildcard }
:   In a project file, `environments: "*"` (and the same for layers, computes and roles) means
    every enabled item; in a user's role entry it means every environment of that project.

`workspace.yaml` { #workspace-yaml }
:   The authoritative list of Dagster code locations. `just start` and `just validate` both read
    it.

Write disposition (dlt) { #write-disposition }
:   What a load does to existing rows: `merge` (upsert on the primary key, the default here),
    `replace` (rewrite the table) or `append`.
