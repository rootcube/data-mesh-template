---
icon: material/rocket-launch
---

# Getting started

From a fresh clone to a running Dagster UI that loads data into your personal schemas of the
project's development database. Four steps, each one page:

1. [Prerequisites](prerequisites.md): `just`, git, and what your platform administrator gives you.
2. [Installation](installation.md): `just init` installs uv, the Python environment and the dbt packages.
3. [Snowflake authentication](snowflake-auth.md): `just snowflake setup` logs you in once and switches you to key-pair authentication.
4. [First run](first-run.md): `just start`, materialize the KNMI weather load and build the dbt models.

Something off? [Troubleshooting](troubleshooting.md) covers the usual suspects.

!!! info "Engineers only"
    These pages are for engineers who work in the repository. Nothing here needs Terraform.
    If you are setting up the Snowflake account or onboarding people, go to
    [Administration](../administration/index.md).

## Checklist

- [ ] `just` and git installed
- [ ] From your administrator: the account identifier, your login, your engineer role, the development database and the warehouse (plus a one-time password if the user was created for you)
- [ ] `just init` finished without errors
- [ ] `just snowflake setup` registered your key and wrote `.env`
- [ ] `just snowflake check` shows your role, warehouse, database and personal layer schemas
- [ ] `just start` shows two code locations loaded at <http://localhost:3000>

## Where you end up

After setup, this is your context in the starter project:

| Setting | Value |
|---------|-------|
| Environment | `dev` |
| Role | `RL_EXAMPLE_DEV__ENG`, the project's engineer role |
| Database | `DB_EXAMPLE_DEV`, shared with every engineer of the project |
| Warehouse | `WH_EXAMPLE_DEV` |
| Your schemas | `DBT_<NAME>_SRC`, `DBT_<NAME>_STG`, `DBT_<NAME>_INT`, ..., created on demand by dlt and dbt |

The names follow the platform model: one database per project and environment, one schema per
layer, one role per purpose. [Concepts](../concepts/index.md) explains it; you do not need it
to get running.
