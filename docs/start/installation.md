---
icon: material/download
---

# Installation

One clone and one command. With `just` and git in place
([Prerequisites](prerequisites.md)):

```bash
git clone https://github.com/rootcube/data-mesh-template.git
cd data-mesh-template
just init
```

With a GitHub SSH key in place, `git clone git@github.com:rootcube/data-mesh-template.git` does
the same; HTTPS needs nothing set up.

## What `just init` does

It is idempotent, so run it again whenever something looks stale. In order:

1. Installs **uv** if it is missing (macOS and Linux via the official install script, Windows via PowerShell).
2. Deletes `.venv/` when the checkout has moved since it was created: its scripts hold the old path.
3. Runs `uv sync --all-groups`: creates `.venv/` with Python 3.13 and installs the locked dependencies, the docs tooling included (Dagster, dlt, dbt, the Snowflake connector, ruff, ty, pytest, sqlfluff, and dbt-duckdb for offline dbt parsing and linting).
4. Reinstalls the git pre-commit hook if you have one, for the same reason. It does not install one; `just pre-commit-install` does that.
5. Copies `.env.example` to `.env` if you have no `.env` yet.
6. Creates the local state folders `.dagster/` and `.dlt/data/`.
7. Runs `dbt deps` in every dbt project (installs `dbt_utils` and links `dbt_common`).
8. Runs `dbt parse --target dummy` in every dbt project, so `just validate` has a manifest to read.
9. Runs `direnv allow` when direnv is installed (macOS and Linux only).

It ends with `Done. Next: just setup`. `just setup` runs `init` itself and then asks one question:
a fresh account you hold `ACCOUNTADMIN` on gets the full bootstrap and provisioning
([Snowflake trial account](../operate/snowflake-trial-account-setup.md)); a platform an
administrator provisioned gets the key-pair setup of
[Snowflake authentication](snowflake-auth.md), which you can also run directly as `just sf setup`.

## Check it worked

```bash
just info
```

prints the tool and package versions plus the status of `.env`, your private key and the local
state folders. Right after `init`, expect
`.env present (missing: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_PATH)`. Filling
those in is the next step; the role, warehouse and database of the starter project are already in
`.env.example`.

## Optional tools

Now that the checkout exists, `just install <tool>` handles the tools uv does not manage, through
Homebrew on macOS and Linux and winget on Windows:

| Tool | Needed for |
|------|------------|
| `terraform` | The fresh-account path of `just setup`, which installs it for you when missing, and everything under [Operate](../operate/index.md); Homebrew installs it through tfenv |
| `tfenv` | macOS and Linux only: the Terraform version manager on its own, without installing a Terraform version |
| `direnv` | Activates `.venv` and loads `.env` when you `cd` into the checkout (the repo ships an `.envrc`), which `just` already does for its own recipes |
| `gh` | The GitHub CLI, for pull requests from the terminal |
| `all` | `uv`, `terraform` and `direnv`; `gh` stays optional and is not part of it |

Engineers on a provisioned platform need none of them.

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

Next: `just setup`, or [Snowflake authentication](snowflake-auth.md) for what its
provisioned-account path does.
