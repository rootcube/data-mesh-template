---
icon: material/variable
---

# Environment variables

All local configuration lives in `.env` (git-ignored, copied from `.env.example` by
`just init`). `just` loads it into every recipe; `.envrc` loads it for direnv users.
`just sf setup` writes the Snowflake block for you.

!!! warning "Quoting"
    Leave values unquoted where you can: `SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG`. A value with
    spaces, `#`, `$` or other special characters goes in single quotes, which `just` and
    python-dotenv both strip, reading the inside literally; Docker's `--env-file` keeps them as
    part of the value. `just sf setup` writes a value bare when it holds only letters, digits and
    `_./:@+,=-`, single-quoted otherwise, and refuses what single quotes cannot carry: a single
    quote, a line break, `\\`, `\'`, a trailing backslash or `${`.

## Engineer settings

| Variable | Example | Meaning |
|----------|---------|---------|
| `ENVIRONMENT` | `dev` | The environment this checkout runs as: `dev` (personal schemas, the default), or `tst`, `acc` or `prd` (the shared `_<LAYER>` schemas, for deployed service users) |
| `SNOWFLAKE_ACCOUNT` | `MYORG-MYACCOUNT` | Account identifier as `<organization>-<account>` |
| `SNOWFLAKE_USER` | `USERNAME@EXAMPLE.COM` | Your login, exactly as `CURRENT_USER()` returns it |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | `/Users/username/.snowflake/keys/....p8` | Absolute path of the private key `just sf setup` wrote |
| `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | empty | Only set when your key is encrypted: `just sf setup --passphrase`, or the passphrase `just sf bootstrap` asks for |
| `SNOWFLAKE_ROLE` | `RL_EXAMPLE_DEV__ENG` | Your engineer role in the project |
| `SNOWFLAKE_WAREHOUSE` | `WH_EXAMPLE_DEV` | The project's warehouse |
| `SNOWFLAKE_DATABASE` | `DB_EXAMPLE_DEV` | The project database of that environment |
| `SNOWFLAKE_SCHEMA` | `DBT_USERNAME` | Prefix of your personal schemas in `dev` (`<prefix>_SRC`, `<prefix>_STG`, ...), which Terraform provisions under the `schema_prefix` of your user file or `DBT_<USERNAME>`; also dbt's schema for models without a layer. Empty in `.env.example`: `just sf setup` fills it in (and leaves it empty for a `tst`, `acc` or `prd` role) |

`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`, `SNOWFLAKE_ROLE`,
`SNOWFLAKE_WAREHOUSE` and `SNOWFLAKE_DATABASE` are required; `just info` and
`just sf check` report which are missing. The single reader is
`SnowflakeSettings.from_env()` in `src/orchestrator/resources/snowflake.py`; `dbt/profiles.yml`
reads the same names with `env_var()`, and `dbt/dbt_example/sources/src_knmi.yml` finds the
source layer from the dbt target (`target.name`, and `target.schema`, which the profile reads
from `SNOWFLAKE_SCHEMA`).

## How the values become schema names

| `ENVIRONMENT` | `SNOWFLAKE_SCHEMA` | dlt loads into | dbt model with `+schema: stg` | dbt model without `+schema` |
|---------------|--------------------|----------------|-------------------------------|-----------------------------|
| `dev` | `DBT_USERNAME` | `DBT_USERNAME_SRC` | `DBT_USERNAME_STG` | `DBT_USERNAME` |
| `dev` | empty | `DBT_SRC` | `DBT_STG` | `DBT` |
| `prd` | empty | `_SRC` | `_STG` | `_TMP` |

In `dev`, set the prefix (`just sf setup` does); the second row is what happens when it is
empty: dlt, Dagster and dbt all fall back to the placeholder prefix `DBT`, nobody has `DBT_*`
schemas, so the load or the run fails loudly instead of writing into the shared `_<LAYER>`
schemas. The last column is not provisioned in `dev` either, so every model needs a layer. The
rule is
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
| `TF_VAR_SNOWFLAKE_ORGANIZATION` | required | Organization part of the account identifier (`MYORG` in `MYORG-MYACCOUNT`) |
| `TF_VAR_SNOWFLAKE_ACCOUNT` | required | Account part (`MYACCOUNT`) |
| `TF_VAR_SNOWFLAKE_USER` | `TERRAFORM_USER` | Service user created by `terraform/modules/snowflake/init.sql` |
| `TF_VAR_SNOWFLAKE_WAREHOUSE` | `WH_PLATFORM_PROVISIONING` | Warehouse for the provider's own queries |
| `TF_VAR_SNOWFLAKE_PRIVATE_KEY_PATH` | `~/.snowflake/keys/terraform.p8` | Private key of the service user (`just sf keygen terraform`) |
| `TF_VAR_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | empty | Passphrase of that key, empty when it is not encrypted; `just sf bootstrap` asks for it and writes it |

There is no role variable: the providers in `terraform/providers.tf` connect as `SYSADMIN`,
`SECURITYADMIN` and `USERADMIN`, which `init.sql` grants to the service user.
