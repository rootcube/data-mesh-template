---
icon: material/clipboard-check
---

# Prerequisites

## Tools

Two tools you install yourself, [`just`](https://github.com/casey/just) and git. `just init`
takes care of everything else (uv, Python 3.13, the virtual environment, the dbt packages).

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

### Optional tools

Once the checkout exists, `just install <tool>` installs the tools uv does not manage, through
Homebrew on macOS and Linux and winget on Windows:

| Tool | Needed for |
|------|------------|
| `terraform` | The fresh-account path of `just setup`, which installs it for you when missing, and everything under [Administration](../administration/index.md); Homebrew installs it through tfenv |
| `direnv` | Optional: activates `.venv` and loads `.env` when you `cd` into the checkout (the repo ships an `.envrc`), which `just` already does for its own recipes |
| `gh` | The GitHub CLI, for pull requests from the terminal |
| `all` | All of the above |

Engineers on a provisioned platform need none of them.

## Access to Snowflake

Your platform administrator provisions the project with Terraform (see
[Administration](../administration/index.md)) and grants your login the engineer role of the
project in development. Ask for:

!!! tip "No platform yet? A Snowflake trial account works"
    For a first test drive, sign up for a free [Snowflake trial](https://signup.snowflake.com/)
    (30 days, no card). Your trial login is `ACCOUNTADMIN`, so `just setup` bootstraps the
    account, provisions the `example` project and fills in `.env` from the organization name,
    the account name, your username and password, and installs Terraform when it is missing.
    Step by step: [Snowflake Trial Account setup](../administration/snowflake-trial-account-setup.md),
    and the table below then answers itself.

| What | Example | Ends up in |
|------|---------|------------|
| Account identifier, `<organization>-<account>` | `MYORG-MYACCOUNT` | `SNOWFLAKE_ACCOUNT` |
| Your login | `username@example.com` | the one-time interactive login, then `SNOWFLAKE_USER` |
| Your engineer role | `RL_EXAMPLE_DEV__ENG` | `SNOWFLAKE_ROLE` |
| The development database | `DB_EXAMPLE_DEV` | `SNOWFLAKE_DATABASE` |
| The warehouse | `WH_EXAMPLE_DEV` | `SNOWFLAKE_WAREHOUSE` |
| A one-time password | only when the administrator created your user | the first login, then you change it |

The development database is shared by every engineer of the project. The same Terraform apply
that grants your role creates your personal schemas in it (`DBT_<USERNAME>_SRC`,
`DBT_<USERNAME>_STG`, ...); dlt and dbt write into them but cannot create schemas, so that apply
comes before your first run. Other engineers use their own prefix, so nobody steps on anyone
else's tables.

## Terraform

Not needed for engineers on a provisioned platform. Platform administrators and the
fresh-account path of `just setup` run Terraform 1.5 or newer; `just setup` installs it when
missing, `just install terraform` does the same by hand. See
[Snowflake provisioning](../administration/snowflake-provisioning.md).

Next: [Installation](installation.md).
