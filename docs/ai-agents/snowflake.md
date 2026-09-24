---
icon: material/snowflake
---

# Snowflake

Snowflake is the only data store: dlt lands source data there, every dbt model builds there, and every project has one database per environment. This page is the agent-facing operational guide: what the platform model looks like as Snowflake objects, the one settings object every tool reads, key-pair authentication, the shared macros, and how to check your work with the `just sf` recipes. The canonical rules (concepts, provisioning, variables) live on the linked pages; do not restate or re-derive them.

## The platform model in Snowflake

Platform administrators provision everything with Terraform from the YAML under `terraform/config/` ([Snowflake provisioning](../administration/snowflake-provisioning.md)); engineers never run Terraform. What one project becomes, per `terraform/main.tf` and the modules under `terraform/modules/snowflake/`:

| Concept | Snowflake object | Example (`example` project) |
|---|---|---|
| Project × Environment | database `DB_<PROJECT>_<ENV>`; the `PUBLIC` schema is dropped | `DB_EXAMPLE_DEV`, `DB_EXAMPLE_PRD` |
| Layer | schema `_<LAYER>` in that database | `_SRC`, `_REF`, `_STG`, `_INT`, `_MRT`, `_EXP`, `_MTD`, `_TMP` |
| Role | account role `RL_<PROJECT>_<ENV>__<PURPOSE>` with grants per layer and per warehouse | `RL_EXAMPLE_DEV__ENG`, `RL_EXAMPLE_PRD__TFM` |
| Compute | warehouse `WH_<PROJECT>_<ENV>` for the default compute, `WH_<PROJECT>_<ENV>__<COMPUTE>_<SIZE>` for the others | `WH_EXAMPLE_DEV` |
| User | role grants to a login (and optionally the user itself), `terraform/config/users/` | `username@example.com` gets `RL_EXAMPLE_DEV__ENG` |

`terraform/config/projects/example.yaml` lists what the starter project provisions: environments `development` and `production`, the eight layers above, the `default` compute (X-Small, auto-suspend after 60 seconds) and the roles `ingest`, `transform`, `engineer`, `analyst`. Environment codes are `dev`, `tst`, `acc`, `prd` (`terraform/config/environments/`). Databases keep one day of Time Travel unless the module is told otherwise.

The four purposes, from `terraform/config/roles/`:

| Role | Purpose code | Type | What it may do |
|---|---|---|---|
| Engineer | `ENG` | person | Full read and write on every layer in `dev` plus `CREATE SCHEMA` on the `dev` database (personal schemas); read-only on the layers in `prd`; read and write on `_TMP` everywhere. Inherits `transform` and `ingest` in `dev` and `tst`, `analyst` everywhere. |
| Analyst | `ANL` | person | Read on `_MRT` and `_EXP`, read and write on `_TMP`, `USAGE` on the default warehouse. |
| Ingest | `ING` | system | Write on `_SRC`, plus tables in `_TMP` for the staging tables of `merge` loads: what dlt runs as in deployed environments. |
| Transform | `TFM` | system | Read on `_SRC`, write on `_STG` to `_EXP`, `_REF`, `_MTD`, `_TMP`: what dbt runs as in deployed environments. |

Behind Terraform sit the bootstrap objects from `terraform/modules/snowflake/init.sql`, created once as `ACCOUNTADMIN`: the service user `TERRAFORM_USER` (key pair only, no password), the role `RL_PLATFORM_PROVISIONING`, the warehouse `WH_PLATFORM_PROVISIONING`, the database `DB_PLATFORM_PROVISIONING` and the resource monitor `RM_PLATFORM_PROVISIONING`. The provider authenticates as that user with `TF_VAR_SNOWFLAKE_*` from `.env` (the commented block at the bottom of `.env.example`).

## Development: personal schemas in a shared database

Every engineer holds `RL_<PROJECT>_DEV__ENG` on the same `DB_<PROJECT>_DEV`. To keep people out of each other's way, `dev` does not use the `_<LAYER>` schemas; each engineer gets personal copies prefixed with `SNOWFLAKE_SCHEMA` (`DBT_<USERNAME>`, written by `just sf setup`), created on demand by dlt and dbt:

| Layer | `dev` (prefix `DBT_USERNAME`) | `tst`, `acc`, `prd` | Written by |
|---|---|---|---|
| Source | `DBT_USERNAME_SRC` | `_SRC` | dlt: `<source>__<entity>` tables plus dlt's `_dlt_*` bookkeeping (`KNMI__CLIMATE_HOURLY`) |
| Reference | `DBT_USERNAME_REF` | `_REF` | dbt seeds |
| Staging, integration, mart, expose | `DBT_USERNAME_STG`, `_INT`, `_MRT`, `_EXP` | `_STG`, `_INT`, `_MRT`, `_EXP` | dbt models (`02_stg` to `05_exp`) |
| Metadata | `DBT_USERNAME_MTD` | `_MTD` | dbt (`dbt_common` hook): `pre__dbt__*` run metadata, created on demand by the first real run |
| Temporary | `DBT_USERNAME_TMP` | `_TMP` | dbt: stored test failures, also `target.schema` outside `dev`; dlt: the staging tables of `merge` loads (`staging_dataset_name_layout`) |
| (no layer) | `DBT_USERNAME` | `_TMP` | dbt models without a `+schema` config (`target.schema`) |

Three pieces of code implement that one rule; keep them in step:

- `SnowflakeSettings.schema_for_layer(layer)` in `src/orchestrator/resources/snowflake.py`: `<SNOWFLAKE_SCHEMA>_<LAYER>` when `ENVIRONMENT` is `dev` (or `dummy`) and a prefix is set, else `_<LAYER>`. dlt uses it for `dataset_name`.
- `dbt_common.generate_schema_name` in `dbt/dbt_common/macros/generate_schema_name.sql`: the same, keyed on `target.name` and `target.schema`.
- The `schema` expression in `dbt/dbt_example/sources/src_knmi.yml`, spelled out with `env_var` because source YAML cannot call macros.

!!! note "Qualify with the schema, not the database"
    Your session database is the project database, so `dbt_username_src.knmi__climate_hourly` or `dbt_username_stg.stg__knmi__climate_hourly` is enough in `dev`. Fully qualified: `DB_EXAMPLE_DEV.DBT_USERNAME_STG.STG__KNMI__CLIMATE_HOURLY`. Snowflake folds unquoted identifiers to upper case, so `dbt_username_stg` and `DBT_USERNAME_STG` are the same schema.

Layer semantics and materialization defaults: [Layers in practice](../architecture/layers.md) and [Snowflake](../architecture/snowflake.md); the concepts: [Layer](../concepts/layer.md), [Role](../concepts/role.md), [Compute](../concepts/compute.md), [Environment](../concepts/environment.md).

## One settings object, key-pair auth everywhere

`SnowflakeSettings.from_env()` in `src/orchestrator/resources/snowflake.py` is the single reader of the `SNOWFLAKE_*` variables (`ACCOUNT`, `USER`, `PRIVATE_KEY_PATH`, `PRIVATE_KEY_PASSPHRASE`, `ROLE`, `WAREHOUSE`, `DATABASE`, `SCHEMA`) and of `ENVIRONMENT` (lower-cased, default `dev`). It is a frozen dataclass; blank variables keep the field default, `missing()` lists what is still unset, and every consumer gets its own view:

| Method | Consumer |
|---|---|
| `schema_for_layer(layer)` | The layer-to-schema rule above; `is_personal` is true for `dev` and `dummy` |
| `dlt_credentials()` | The dlt destination, `dlt_pipelines/utils/destination.py` |
| `connect()` / `connection_kwargs()` | Plain `snowflake.connector` connections (`scripts/snowflake.py`); the connection carries `application = DATA_MESH_STARTER` |
| `private_key_der()` | The PEM key as unencrypted PKCS#8 DER, the form the connector accepts |

`dbt/profiles.yml` reads the same variable names with `env_var()`, so there is exactly one place to look when a connection fails. Extend this class rather than opening ad-hoc connections in asset code.

Authentication is key pair only, no passwords in files:

- `just sf setup` does the one-time interactive login (browser by default, `--auth password` for password plus MFA), writes an RSA 2048 key pair to `~/.snowflake/keys/<account>__<user>.p8` and `.pub`, registers the public key with `ALTER USER ... SET RSA_PUBLIC_KEY`, verifies key-pair login (with a few retries, a fresh key can take a moment), asks you to confirm role, warehouse, database and personal schema prefix (defaults from your user's settings, prefix `DBT_<first part of your login>`), and writes `.env` including `ENVIRONMENT`. `--slot 2` registers into `RSA_PUBLIC_KEY_2` for rotation; `--passphrase` encrypts the private key; `--yes` skips the confirmation.
- `just sf check` connects with the key pair and prints organization, account, user, role, warehouse, database, schema and version, the schemas that exist in your database, and the layer schemas it resolves for your environment.
- `just sf query "SELECT 1"` runs one statement (`--limit 50` rows by default).
- `just sf keygen <name>` creates a key pair without logging in and prints the public key body, for service users: `just sf keygen terraform` is step one of the administrator bootstrap; the ingest and transform system users of deployed environments get theirs the same way.

The walkthrough: [Snowflake authentication](../getting-started/snowflake-auth.md); every variable: [Environment variables](../reference/environment-variables.md); onboarding people and system users: [Onboarding](../administration/onboarding.md).

!!! warning "No quotes in `.env`"
    `just` and Docker pass quoted values literally, which breaks identifiers and the key path. `just sf setup` writes the file unquoted; keep it that way when editing by hand.

## Shared macros

Snowflake-specific machinery lives in `dbt/dbt_common/macros/`, picked up by every project through its `dispatch` order (`["dbt_common", "dbt"]`). Call them namespaced: `dbt_common.<macro>`.

| Macro | Purpose |
|---|---|
| `generate_schema_name` | The layer-to-schema rule: `<target.schema>_<LAYER>` on the `dev` and `dummy` targets, `_<LAYER>` elsewhere, `target.schema` when a model has no `+schema`. Overrides dbt's default `<target>_<custom>` naming. |
| `set_query_tag` | Tags every session with `dbt_invocation_id:<invocation_id>`, so a whole run is one filter in the query history. |
| `log_run_info` | `on-run-start` banner: invocation id, target, organization, account, database, warehouse, threads, user, plus Snowsight links to the catalog and to the run's queries by tag. |
| `log_run_summary` | `on-run-end` summary: totals by status, slowest models, failed tests, total runtime. |
| `upload_results` | `on-run-end` upload of run metadata into `pre__dbt__*` tables in the metadata layer (vendored `dbt_artifacts` upload machinery, Snowflake-only trim; `macros/dbt_artifacts/README.md` explains what was kept). Creates the personal metadata schema (`<prefix>_MTD`) in `dev` and the tables if they do not exist; elsewhere `_MTD` is provisioned. Skipped on the `dummy` target; `default_fallbacks.sql` provides `default__` variants so the DuckDB parse still resolves dispatch. |
| `search_optimization(this, operations)` | Post-hook: `ALTER TABLE ... ADD SEARCH OPTIMIZATION`, default `EQUALITY(*), SUBSTRING(*)`; renders nothing for views and ephemeral models. |
| `utc_now` / `utc_today` | `SYSDATE()` based, independent of the session `TIMEZONE`; use instead of `CURRENT_TIMESTAMP()` / `CURRENT_DATE()`. |
| `format_duration(seconds)` | Seconds to an `HH:MM:SS` string. |
| `terminal_colors` | ANSI colors for the run banner and summary; off unless the dbt var `terminal_colors` is `true`. |

Read a macro's header comment before using it; each documents its inputs.

## Materializations

Defaults come from `dbt/dbt_example/dbt_project.yml`: tables for `_STG`, `_INT` and `_MRT`, views for `_EXP`; `dbt_common` builds its `_INT` models as views. Heavy logic in an `_EXP` view is not a reason to materialize it as a table; push the logic down to `_INT` or `_MRT`.

!!! warning "Python models run inside Snowflake"
    `int__common__holiday` in `dbt_common` is a Snowpark model that imports `holidays` from the Anaconda channel. That works only after an `ORGADMIN` accepted the Anaconda terms once per account. `dbt/` is excluded from ruff and ty for this reason: those files run in Snowflake's Python, not in the repo's venv. Failing with a package error? [Snowflake provisioning](../administration/snowflake-provisioning.md) has the opt-out snippet.

## Checking your work

No MCP server is configured for Snowflake; the recipes cover the same ground.

```bash
just sf check                                                             # who am I, which schemas exist, which layer schemas apply
just sf query "SELECT COUNT(1) FROM dbt_username_src.knmi__climate_hourly"    # did the load land
just sf query "SELECT COUNT(1) FROM dbt_username_stg.stg__knmi__climate_hourly"  # did the model build
just sf query "SHOW TABLES IN SCHEMA dbt_username_mtd"                        # run metadata tables
```

`dbt_username` stands for your own `SNOWFLAKE_SCHEMA` prefix; outside `dev` the schemas are `_SRC`, `_STG` and `_MTD`. For anything larger, the run banner from `log_run_info` prints a Snowsight link filtered on the run's query tag; open it to see every statement dbt executed with timings.

## What an agent may touch on the administrator side

Editing `terraform/config/*.yaml` is safe and checkable: `just tf-validate-config` validates every file against its JSON schema and the cross-references. A new project is a copy of `projects/example.yaml` with its own `code`; a new person is a file under `users/` listing project roles per environment. Anything beyond that (`just tf plan`, `just tf apply`, `init.sql`, registering keys on other users) is a human administrator's call; describe the change and stop.

## Source files

- Settings: `src/orchestrator/resources/snowflake.py`
- Key-pair setup and the query helper: `scripts/snowflake.py`
- `.env` editing that keeps comments intact: `src/orchestrator/utils/dotenv.py`
- Shared dbt profiles: `dbt/profiles.yml`
- Schema routing: `dbt/dbt_common/macros/generate_schema_name.sql`
- Metadata upload: `dbt/dbt_common/macros/dbt_artifacts/`
- Provisioning (administrators): `terraform/main.tf`, `terraform/users.tf`, `terraform/config/`, `terraform/modules/snowflake/init.sql`

## Related pages

- [Snowflake](../architecture/snowflake.md): the project database from the architecture angle
- [Layers in practice](../architecture/layers.md): the schema-per-layer map and materialization defaults
- [Concepts](../concepts/index.md): organisation, team, project, environment, layer, role, compute
- [Snowflake authentication](../getting-started/snowflake-auth.md): the setup walkthrough
- [Snowflake provisioning](../administration/snowflake-provisioning.md): what Terraform creates and how
- [Environment variables](../reference/environment-variables.md): every `SNOWFLAKE_*` variable and who reads it
- [Troubleshooting](../getting-started/troubleshooting.md): `JWT token is invalid` and friends
