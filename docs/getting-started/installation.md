---
icon: material/download
---

# Installation

## Tools

Two tools you install yourself, [`just`](https://github.com/casey/just) and git. `just init`
takes care of everything else.

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

## Clone and init

```bash
git clone git@github.com:rootcube/data-mesh-template.git
cd data-mesh-template
just init
```

`just init` is idempotent and does, in order:

1. Installs **uv** if it is missing (macOS/Linux via the official install script, Windows via PowerShell).
2. Runs `uv sync --all-groups`: creates `.venv/` with Python 3.13 and installs the locked dependencies, the docs tooling included
   (Dagster, dlt, dbt, the Snowflake connector, ruff, ty, pytest, sqlfluff, and dbt-duckdb for
   offline dbt parsing and linting).
3. Copies `.env.example` to `.env` if you have no `.env` yet.
4. Creates the local state folders `.dagster/` and `.dlt/data/`.
5. Runs `dbt deps` in every dbt project (installs `dbt_utils` and links `dbt_common`).
6. Runs `direnv allow` when direnv is installed.

It ends with `Done. Next: just setup`. `just setup` runs `init` itself and then asks one
question: a fresh account you hold `ACCOUNTADMIN` on gets the full bootstrap and provisioning
([Snowflake Trial Account setup](../administration/snowflake-trial-account-setup.md)); a
platform an administrator provisioned gets the key-pair setup of
[Snowflake authentication](snowflake-auth.md), which you can also run directly as `just sf setup`.

## Optional tools

Once the checkout exists, `just install <tool>` installs the tools uv does not manage, through
Homebrew on macOS and Linux and winget on Windows:

| Tool | Needed for |
|------|------------|
| `terraform` | The fresh-account path of `just setup`, which installs it for you when missing, and everything under [Administration](../administration/index.md); Homebrew installs it through tfenv |
| `direnv` | Optional: activates `.venv` and loads `.env` when you `cd` into the checkout, which `just` already does for its own recipes |
| `gh` | The GitHub CLI, for pull requests from the terminal |
| `all` | All of the above |

## Verify

```bash
just info
```

prints the tool and package versions plus the status of `.env`, your private key and the local
state folders. Right after `init`, expect
`.env present (missing: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_PATH)`:
filling those in is the next step. The role, warehouse and database of the starter project are
already in `.env.example`.

## What is where

| Path | Contents |
|------|----------|
| `justfile` | Every command; run `just` to list them |
| `src/orchestrator/` | The Dagster package: code locations and the shared Snowflake settings |
| `dlt_pipelines/` | dlt ingest pipelines, one folder per source |
| `dbt/` | `profiles.yml`, the shared `dbt_common` package, and the `dbt_example` project |
| `terraform/` | Snowflake provisioning from YAML (administrators only) |
| `scripts/` | `snowflake.py` (bootstrap, key-pair setup, check, query), `info.py`, `dbt_all.py` |
| `tests/` | pytest, offline only |
| `docs/` | This site (`just docs`) |
| `.env` | Your personal settings, git-ignored |
| `.dagster/`, `.dlt/data/` | Local Dagster and dlt state, git-ignored |

Next: `just setup`, or [Snowflake authentication](snowflake-auth.md) for what its provisioned-account
path does.
