---
icon: material/download
---

# Installation

```bash
git clone git@github.com:rootcube/enexis-dev-day.git
cd enexis-dev-day
just init
```

`just init` is idempotent and does, in order:

1. Installs **uv** if it is missing (macOS/Linux via the official install script, Windows via PowerShell).
2. Runs `uv sync`: creates `.venv/` with Python 3.13 and installs the locked dependencies
   (Dagster, dlt, dbt, the Snowflake connector, ruff, ty, pytest, sqlfluff, and dbt-duckdb for
   offline dbt parsing and linting).
3. Copies `.env.example` to `.env` if you have no `.env` yet.
4. Creates the local state folders `.dagster/` and `.dlt/data/`.
5. Runs `dbt deps` in every dbt project (installs `dbt_utils` and links `dbt_common`).
6. Runs `direnv allow` when direnv is installed.

It ends with `Done. Next: just snowflake setup`.

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
| `scripts/` | `snowflake.py` (key-pair setup), `info.py`, `dbt_all.py` |
| `tests/` | pytest, offline only |
| `docs/` | This site (`just docs`) |
| `.env` | Your personal settings, git-ignored |
| `.dagster/`, `.dlt/data/` | Local Dagster and dlt state, git-ignored |

Next: [Snowflake authentication](snowflake-auth.md).
