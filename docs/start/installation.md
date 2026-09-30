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
6. Creates the local state folders `.dagster/`, `.dlt/data/` and `.duckdb/data/`.
7. Runs `dbt deps` in every dbt project (installs `dbt_utils` and links `dbt_common`).
8. Runs `dbt parse --target local` in every dbt project, so `just validate` has a manifest to read.
9. Runs `direnv allow` when direnv is installed (macOS and Linux only).

It ends with `Done. Next: just setup`. `just setup` runs `init` itself and then asks one question:
a fresh account you hold `ACCOUNTADMIN` on gets the full bootstrap and provisioning
([Snowflake trial account](../operate/snowflake-trial-account-setup.md)); a platform an
administrator provisioned gets the key-pair setup of
[Snowflake authentication](snowflake-auth.md), which you can also run directly as `just sf setup`.
No Snowflake account at all? [Local only, no Snowflake](#local-only-no-snowflake) below.

## Check it worked

```bash
just info
```

prints the tool and package versions plus the status of `.env`, your private key and the local
state folders. Right after `init`, expect
`.env present (missing: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_PATH)`. Filling
those in is the next step; the role, warehouse and database of the starter project are already in
`.env.example`.

## Local only, no Snowflake

No Snowflake account, no key pair, no Terraform. `just sf local` (or `just setup`, option
`4  Local only`) writes `ENVIRONMENT=local` to `.env` and nothing else.

dlt and dbt then build against a DuckDB file instead of Snowflake, at the path `DUCKDB_PATH`
points at (`.duckdb/data/local.duckdb`, exported by the justfile and `.envrc`; `just init`
creates `.duckdb/data`). Everything else works the same:

- `just start`: the Dagster UI, the same two code locations.
- `just dlt run knmi`, or materializing an asset: loads into the DuckDB file.
- `just dbt build`: builds and tests the models in the same file.
- Open the file directly: `duckdb .duckdb/data/local.duckdb` (the `duckdb` CLI), or from Python
  with `duckdb.connect(".duckdb/data/local.duckdb")`.

`just info` shows a local block instead of the Snowflake context: `ENVIRONMENT=local`, the
DuckDB file path and whether it exists yet, and what to run next.

What is different in local mode:

- No `_MTD` run metadata: the upload is Snowflake-only, so `dbt_common`'s `on-run-end` hook
  skips it. `log_run_summary` still prints.
- No stages or stage refresh: DuckDB has none, so `refresh_stages` skips itself too.
- Schedules and sensors start stopped, same as `dev`.
- A DuckDB file has one writer at a time: two runs that touch it together, or `just check`'s
  sqlfluff lint while a run is active, fail with a lock error. Fine for one engineer working
  alone; see [Orchestration](../understand/orchestration.md#the-local-instance).

`just reset-local` deletes `.duckdb/` along with the rest of the local state and recreates the
directory. Next: `just start`, or `just dlt run knmi` and then `just dbt build`.

## Optional tools

Now that the checkout exists, `just install <tool>` handles the tools uv does not manage, through
Homebrew on macOS and Linux and winget on Windows:

| Tool | Needed for |
|------|------------|
| `terraform` | The fresh-account path of `just setup`, which installs it for you when missing, and everything under [Operate](../operate/index.md); Homebrew installs it through tfenv |
| `tfenv` | macOS and Linux only: the Terraform version manager on its own, without installing a Terraform version |
| `atmos` | Runs Terraform once per project and environment ([Stacks and state](../operate/snowflake-provisioning.md#stacks-and-state)); needed wherever `terraform` is. Homebrew on macOS and Linux; on Windows Scoop when you have it, otherwise the release the justfile pins, checked against its checksums, into `~\.local\bin` |
| `direnv` | Activates `.venv` and loads `.env` when you `cd` into the checkout (the repo ships an `.envrc`), which `just` already does for its own recipes |
| `gh` | The GitHub CLI, for pull requests from the terminal |
| `all` | `uv`, `terraform`, `atmos` and `direnv`; `gh` stays optional and is not part of it |

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
provisioned-account path does, or [Local only, no Snowflake](#local-only-no-snowflake) above for
no Snowflake at all.
