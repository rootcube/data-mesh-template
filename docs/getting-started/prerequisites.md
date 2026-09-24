---
icon: material/clipboard-check
---

# Prerequisites

## Tools

You install two things yourself; `just init` takes care of the rest (uv, Python 3.13, the
virtual environment, the dbt packages).

=== "macOS / Linux"

    ```bash
    brew install just git
    ```

=== "Windows"

    ```powershell
    winget install --id Casey.Just -e
    winget install --id Git.Git -e
    ```

    Every `just` command in these docs works in PowerShell exactly as shown.

!!! note "No Python install needed"
    [uv](https://docs.astral.sh/uv/) provisions the pinned interpreter (Python 3.13, from
    `.python-version`) inside the project's `.venv`. You never activate it by hand: every
    command runs through `uv run`.

[direnv](https://direnv.net/) is optional. The repo ships an `.envrc` that activates `.venv`
and loads `.env` when you `cd` into it, but `just` does the same for its own recipes.

## Access to Snowflake

Your platform administrator provisions the project with Terraform (see
[Administration](../administration/index.md)) and grants your login the engineer role of the
project in development. Ask for:

!!! tip "No platform yet? A Snowflake trial account works"
    For a first test drive, sign up for a free [Snowflake trial](https://signup.snowflake.com/)
    (30 days, no card). Your trial login is `ACCOUNTADMIN`, which is all the
    [bootstrap](../administration/snowflake-provisioning.md) needs: run it, apply the Terraform
    for the `example` project, add yourself under `terraform/config/users/`, and the table below
    answers itself: the account identifier from the trial's welcome mail, your login,
    `RL_EXAMPLE_DEV__ENG`, `DB_EXAMPLE_DEV` and `WH_EXAMPLE_DEV`.

| What | Example | Ends up in |
|------|---------|------------|
| Account identifier, `<organization>-<account>` | `MYORG-MYACCOUNT` | `SNOWFLAKE_ACCOUNT` |
| Your login | `engineer@example.com` | the one-time interactive login, then `SNOWFLAKE_USER` |
| Your engineer role | `RL_EXAMPLE_DEV__ENG` | `SNOWFLAKE_ROLE` |
| The development database | `DB_EXAMPLE_DEV` | `SNOWFLAKE_DATABASE` |
| The warehouse | `WH_EXAMPLE_DEV` | `SNOWFLAKE_WAREHOUSE` |
| A one-time password | only when the administrator created your user | the first login, then you change it |

The development database is shared by every engineer of the project. The engineer role holds
`CREATE SCHEMA` on it, and dlt and dbt create your personal schemas (`DBT_<NAME>_SRC`,
`DBT_<NAME>_STG`, ...) on first use. Other engineers use their own prefix, so nobody steps on
anyone else's tables.

## Terraform

Not needed for engineers. Only platform administrators run Terraform (1.5 or newer, see
[Snowflake provisioning](../administration/snowflake-provisioning.md)).

Next: [Installation](installation.md).
