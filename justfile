# Task runner for the platform. Requires `just` (https://github.com/casey/just):
#   macOS/Linux : brew install just
#   Windows     : winget install --id Casey.Just -e
#
# Everything runs through `uv run`, so no venv activation is needed. Recipes with
# OS-specific bodies carry [unix] / [windows] attributes; the rest is identical on
# all platforms. Run bare `just` to list the recipes.

# Load .env into every recipe (Snowflake settings written by `just snowflake setup`).
set dotenv-load := true
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# Local state lives inside the repo, so deleting .dagster/ and .dlt/data/ resets everything.
export DAGSTER_HOME     := justfile_directory() / ".dagster"
export DLT_PROJECT_DIR  := justfile_directory()
export DLT_DATA_DIR     := justfile_directory() / ".dlt" / "data"
export DBT_PROFILES_DIR := justfile_directory() / "dbt"
# The Snowflake connector's vendored requests warns about urllib3 on every command; nothing to fix here.
export PYTHONWARNINGS := "ignore:::snowflake.connector.vendored.requests"

# Overridable: `just project=dbt_other dbt build` targets another dbt project under dbt/.
project     := "dbt_example"
dbt_project := "dbt" / project
tf_dir      := "terraform"
port        := "3000"

# list recipes (default)
default:
    @just --list --unsorted

# --- Setup ------------------------------------------------------------------

# bootstrap: install uv if missing, create .venv, create .env, install dbt packages
[unix]
init:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv not found, installing..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    # A moved or renamed checkout leaves .venv scripts pointing at the old path; rebuild it.
    if [ -f .venv/bin/activate ] && ! grep -q "^VIRTUAL_ENV='$PWD/.venv'$" .venv/bin/activate; then
        echo "checkout moved since .venv was created, recreating it"
        rm -rf .venv
    fi
    uv sync
    # An installed git hook also carries the venv path; refresh it in the same case.
    if [ -f .git/hooks/pre-commit ]; then uv run pre-commit install >/dev/null; fi
    if [ ! -f .env ]; then cp .env.example .env && echo "created .env from .env.example"; fi
    mkdir -p .dagster .dlt/data
    uv run python scripts/dbt_all.py deps --quiet
    if command -v direnv >/dev/null 2>&1; then direnv allow . >/dev/null 2>&1 || true; fi
    echo ""
    echo "Done. Next: just snowflake setup"

# bootstrap: install uv if missing, create .venv, create .env, install dbt packages
[windows]
init:
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"; $env:Path = "$env:USERPROFILE\.local\bin;$env:Path" }
    if ((Test-Path .venv\Scripts\activate.bat) -and -not (Select-String -Path .venv\Scripts\activate.bat -SimpleMatch "VIRTUAL_ENV=$PWD\.venv" -Quiet)) { Write-Host "checkout moved since .venv was created, recreating it"; Remove-Item -Recurse -Force .venv }
    uv sync
    if (Test-Path .git\hooks\pre-commit) { uv run pre-commit install | Out-Null }
    if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "created .env from .env.example" }
    New-Item -ItemType Directory -Force -Path .dagster, .dlt\data | Out-Null
    uv run python scripts/dbt_all.py deps --quiet
    Write-Host ""; Write-Host "Done. Next: just snowflake setup"

# show tool versions and whether .env and your key pair are in place
info:
    uv run python scripts/info.py

# --- Snowflake --------------------------------------------------------------

# key-pair auth: `just snowflake setup` (one-time), `context` (pick a project), `check`, `query "SELECT 1"`, `keygen <name>`
snowflake cmd *args:
    uv run python scripts/snowflake.py {{cmd}} {{args}}

# --- Dagster ----------------------------------------------------------------

# start the Dagster dev server on http://localhost:3000 (Ctrl+C to stop)
start: _dirs
    uv run dagster dev -w workspace.yaml -h 127.0.0.1 -p {{port}}

# stop whatever is listening on the Dagster port
[unix]
stop:
    @lsof -ti :{{port}} | xargs kill -9 2>/dev/null || echo "nothing listening on port {{port}}"

# stop whatever is listening on the Dagster port
[windows]
stop:
    @$p = Get-NetTCPConnection -LocalPort {{port}} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($p) { Stop-Process -Id $p -Force } else { Write-Host "nothing listening on port {{port}}" }

# run the Dagster CLI, e.g. `just dagster asset list -m orchestrator.locations.dlt.definitions`
dagster *args:
    uv run dagster {{args}}

# load every code location exactly like `just start` does, without the UI
validate:
    uv run dagster definitions validate -w workspace.yaml

# --- dlt --------------------------------------------------------------------

# run a dlt pipeline outside Dagster: `just dlt list`, `just dlt run knmi`
dlt cmd *args: _dirs
    uv run python -m dlt_pipelines {{cmd}} {{args}}

# --- dbt --------------------------------------------------------------------

# run dbt in dbt/dbt_example (override: `just project=dbt_x dbt build`), e.g. `just dbt build`
dbt *args:
    cd {{dbt_project}}; uv run dbt {{args}}

# run one dbt command in every project under dbt/, e.g. `just dbt-all deps`, `just dbt-all parse`
dbt-all *args:
    uv run python scripts/dbt_all.py {{args}}

# lint or fix SQL with sqlfluff from the dbt project, e.g. `just sqlfluff lint models`
sqlfluff *args:
    cd {{dbt_project}}; uv run sqlfluff {{args}}

# --- Terraform (platform administrators) -----------------------------------

# run terraform in terraform/, e.g. `just tf init`, `just tf plan`, `just tf apply`
tf cmd *args:
    cd {{tf_dir}}; terraform {{cmd}} {{args}}

# validate the YAML configuration under terraform/config against its JSON schemas
tf-validate-config:
    uv run python terraform/config/_validation/validate_configs.py

# --- Docs -------------------------------------------------------------------

# serve the docs on http://localhost:8000 (`just docs build` for a static site/)
docs cmd="serve" *args:
    uv run --group docs mkdocs {{cmd}} {{args}}

# --- Quality ----------------------------------------------------------------

# format Python (ruff) and SQL (sqlfluff)
fmt:
    uv run ruff format .
    uv run ruff check --fix .
    cd {{dbt_project}}; uv run sqlfluff fix models

# lint Python and SQL without changing files
lint:
    uv run ruff check .
    uv run ruff format --check .
    cd {{dbt_project}}; uv run sqlfluff lint models

# type check Python with ty
typecheck:
    uv run ty check

# run the tests
test:
    uv run pytest

# everything CI runs: lint, typecheck, tests, dbt parse, Dagster definitions
check: lint typecheck test
    uv run python scripts/dbt_all.py parse --target dummy --quiet
    uv run dagster definitions validate -w workspace.yaml
    uv run python terraform/config/_validation/validate_configs.py

# run all pre-commit hooks on all files
pre-commit:
    uv run pre-commit run --all-files

# install the git pre-commit hook
pre-commit-install:
    uv run pre-commit install

# --- Private helpers --------------------------------------------------------

[private]
_dirs:
    @uv run python -c "import pathlib; [pathlib.Path(p).mkdir(parents=True, exist_ok=True) for p in ('.dagster', '.dlt/data')]"
