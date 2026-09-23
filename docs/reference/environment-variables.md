---
icon: material/variable
---

# Environment variables

All local configuration lives in `.env` (git-ignored, copied from `.env.example` by
`just init`). `just` loads it into every recipe; `.envrc` loads it for direnv users.
`just snowflake setup` writes the Snowflake block for you.

!!! warning "No quotes"
    Write `SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG`, never `"RL_EXAMPLE_DEV__ENG"`. python-dotenv
    strips quotes, but `just` and Docker pass them literally, which breaks identifiers and
    file paths.

## Engineer settings

| Variable | Example | Meaning |
|----------|---------|---------|
| `ENVIRONMENT` | `dev` | The environment this checkout runs as: `dev` (personal schemas, the default), or `prd` (the shared `_<LAYER>` schemas, for deployed service users; `tst` and `acc` need a profile target once enabled) |
| `SNOWFLAKE_ACCOUNT` | `ROOTCUBE-PLATFORM` | Account identifier as `<organization>-<account>` |
| `SNOWFLAKE_USER` | `ENGINEER@EXAMPLE.COM` | Your login, exactly as `CURRENT_USER()` returns it |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | `/Users/you/.snowflake/keys/....p8` | Absolute path of the private key `just snowflake setup` wrote |
| `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | empty | Only set when you chose `--passphrase` |
| `SNOWFLAKE_ROLE` | `RL_EXAMPLE_DEV__ENG` | Your engineer role in the project |
| `SNOWFLAKE_WAREHOUSE` | `WH_EXAMPLE_DEV` | The project's warehouse |
| `SNOWFLAKE_DATABASE` | `DB_EXAMPLE_DEV` | The project database of that environment |
| `SNOWFLAKE_SCHEMA` | `DBT_ENGINEER` | Prefix of your personal schemas in `dev` (`<prefix>_SRC`, `<prefix>_STG`, ...); also dbt's schema for models without a layer |

`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`, `SNOWFLAKE_ROLE`,
`SNOWFLAKE_WAREHOUSE` and `SNOWFLAKE_DATABASE` are required; `just info` and
`just snowflake check` report which are missing. The single reader is
`SnowflakeSettings.from_env()` in `src/orchestrator/resources/snowflake.py`; `dbt/profiles.yml`
reads the same names with `env_var()`, and `dbt/dbt_example/sources/src_knmi.yml` reads
`SNOWFLAKE_SCHEMA` and `ENVIRONMENT` to find the source layer.

## How the values become schema names

| `ENVIRONMENT` | `SNOWFLAKE_SCHEMA` | dlt loads into | dbt model with `+schema: stg` | dbt model without `+schema` |
|---------------|--------------------|----------------|-------------------------------|-----------------------------|
| `dev` | `DBT_ENGINEER` | `DBT_ENGINEER_SRC` | `DBT_ENGINEER_STG` | `DBT_ENGINEER` |
| `dev` | empty | `_SRC` | `DBT_STG` (profile default `DBT`) | `DBT` |
| `prd` | empty | `_SRC` | `_STG` | `_TMP` (profile default) |

In `dev`, set the prefix; the second row is what goes wrong when you do not. The rule is
`SnowflakeSettings.schema_for_layer()` for dlt and Dagster and
`dbt_common.generate_schema_name` for dbt.

## dbt and dlt

| Variable | Default | Purpose |
|----------|---------|---------|
| `DBT_TARGET` | unset, so the target follows `ENVIRONMENT` | Target in `dbt/profiles.yml`: `dev`, `tst`, `acc`, `prd` (Snowflake, key pair) or `dummy` (an in-memory DuckDB that parses, compiles and lints without Snowflake; never connects) |
| `RUNTIME__LOG_LEVEL` | `INFO` in `.env.example`; `WARNING` from `.dlt/config.toml` when unset | dlt log level for local runs; `DEBUG` shows everything |

## Set by the justfile and .envrc

You never set these; both the `justfile` and `.envrc` export them with the same values.

| Variable | Value | Purpose |
|----------|-------|---------|
| `DAGSTER_HOME` | `<repo>/.dagster` | Dagster instance: run history, event logs, `dagster.yaml` |
| `DLT_PROJECT_DIR` | `<repo>` | Where dlt finds `.dlt/config.toml` |
| `DLT_DATA_DIR` | `<repo>/.dlt/data` | dlt working directory |
| `DBT_PROFILES_DIR` | `<repo>/dbt` | The shared `profiles.yml` |
| `PYTHONWARNINGS` | `ignore:::snowflake.connector.vendored.requests` | Silences a urllib3 warning from the Snowflake connector |

CI sets `DBT_TARGET=dummy`, `DBT_PROFILES_DIR` and `DAGSTER_HOME` itself
(`.github/workflows/ci.yml`); no Snowflake credentials exist there.

## Platform administrators (Terraform)

Terraform reads its provider settings from `TF_VAR_*` variables, kept in the same `.env`
(the commented block at the bottom of `.env.example`). They map to `terraform/variables.tf`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `TF_VAR_SNOWFLAKE_ORGANIZATION` | required | Organization part of the account identifier (`ROOTCUBE` in `ROOTCUBE-PLATFORM`) |
| `TF_VAR_SNOWFLAKE_ACCOUNT` | required | Account part (`PLATFORM`) |
| `TF_VAR_SNOWFLAKE_USER` | `TERRAFORM_USER` | Service user created by `terraform/modules/snowflake/init.sql` |
| `TF_VAR_SNOWFLAKE_PROVISIONING_ROLE` | `RL_PLATFORM_PROVISIONING` | Role Terraform provisions with |
| `TF_VAR_SNOWFLAKE_WAREHOUSE` | `WH_PLATFORM_PROVISIONING` | Warehouse for the provider's own queries |
| `TF_VAR_SNOWFLAKE_PRIVATE_KEY_PATH` | `~/.snowflake/keys/terraform.p8` | Private key of the service user (`just snowflake keygen terraform`) |
| `TF_VAR_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | unset | Only when that key is encrypted |
