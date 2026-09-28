---
icon: material/clipboard-check
---

# Prerequisites

Two tools you install yourself, and one conversation with whoever runs your Snowflake account.

## Install just and git

[`just`](https://github.com/casey/just) and git are the only things you need before the clone.
`just init` takes care of the rest: uv, Python 3.13, the virtual environment, the dbt packages.

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

Terraform is not an engineer's tool here. Administrators need it, and so does the fresh-account
path of `just setup`, which installs it for you when it is missing.

## What to ask your administrator for

Your platform administrator provisions the project with Terraform and grants your login the
engineer role in development (their side of it: [Operate](../operate/index.md)). Ask for:

| What | Example | Ends up in |
|------|---------|------------|
| Account identifier, `<organization>-<account>` | `MYORG-MYACCOUNT` | `SNOWFLAKE_ACCOUNT` |
| Your login | `username@example.com` | the one-time interactive login, then `SNOWFLAKE_USER` |
| Your engineer role | `RL_EXAMPLE_DEV__ENG` | `SNOWFLAKE_ROLE` |
| The development database | `DB_EXAMPLE_DEV` | `SNOWFLAKE_DATABASE` |
| The warehouse | `WH_EXAMPLE_DEV` | `SNOWFLAKE_WAREHOUSE` |
| A one-time password | only when the administrator created your user | the first login, then you change it |

The development database is shared by every engineer on the project. The same Terraform apply
that grants your role creates your personal schemas in it (`DBT_<USERNAME>_SRC`,
`DBT_<USERNAME>_STG`, ...); dlt and dbt write into those but cannot create them, so that apply
has to happen before your first run. Every engineer has their own prefix, so nobody lands on
anybody else's tables.

!!! tip "No platform yet? A trial account is enough"
    Sign up for a free [Snowflake trial](https://signup.snowflake.com/) (30 days, no card). Your
    trial login holds `ACCOUNTADMIN`, so `just setup` bootstraps the account, installs Terraform
    if it is missing, provisions the `example` project and fills in `.env` from the organization
    name, the account name, your username and your password. The table above then answers itself.
    Step by step: [Snowflake trial account](../operate/snowflake-trial-account-setup.md).

Next: [Installation](installation.md).
