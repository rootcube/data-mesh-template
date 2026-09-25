# Task runner for the platform. Requires `just` (https://github.com/casey/just):
#   macOS/Linux : brew install just
#   Windows     : winget install --id Casey.Just -e
#
# Everything runs through `uv run`, so no venv activation is needed. Recipes with
# OS-specific bodies carry [unix] / [windows] attributes; the rest is identical on
# all platforms. Run bare `just` to list the recipes.

# Load .env into every recipe (Snowflake settings written by `just sf setup`).
set dotenv-load := true
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# Local state lives inside the repo, so deleting .dagster/ and .dlt/data/ resets everything.
export DAGSTER_HOME     := justfile_directory() / ".dagster"
export DLT_PROJECT_DIR  := justfile_directory()
export DLT_DATA_DIR     := justfile_directory() / ".dlt" / "data"
export DBT_PROFILES_DIR := justfile_directory() / "dbt"
# Two warnings with nothing to fix: the Snowflake connector's vendored requests nags about urllib3 on
# every command, and Dagster's CLI marks `definitions validate` as superseded by `dg check defs`, which
# does not read workspace.yaml (the same filter sits in .pre-commit-config.yaml and ci.yml).
export PYTHONWARNINGS := "ignore:::snowflake.connector.vendored.requests,ignore:Function `definitions_validate_command`"
# uv's installer puts it in ~/.local/bin; each recipe line is a fresh shell, so make it findable
# right after `just init` installs it, before the user restarts their shell.
_uv_bin   := if os_family() == "windows" { home_directory() + "\\.local\\bin" } else { home_directory() / ".local" / "bin" }
_path_sep := if os_family() == "windows" { ";" } else { ":" }
# Same for `just install terraform` on Windows: winget adds its package folder to the user PATH,
# which only shells started after the install pick up.
_tf_bin   := if os_family() == "windows" { env("LOCALAPPDATA", "") + "\\Microsoft\\WinGet\\Packages\\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe" + _path_sep } else { "" }
export PATH := _uv_bin + _path_sep + _tf_bin + env("PATH")

# Overridable: `just project=dbt_other dbt build` targets another dbt project under dbt/.
project     := "dbt_example"
dbt_project := "dbt" / project
tf_dir      := "terraform"
# sqlfluff discovers a config above the working directory only by walking from there to your home
# directory. A checkout on another drive than your profile (Windows) shares no path with it, so the
# shared dbt/.sqlfluff is never found; pass it explicitly and the lookup stops mattering.
sqlfluff_config := justfile_directory() / "dbt" / ".sqlfluff"
port        := "3000"

# list recipes (default)
default:
    @just --list --unsorted

# --- Setup ------------------------------------------------------------------

# bootstrap: install uv if missing, create .venv, create .env, install dbt packages
[unix]
init: _init
    @echo ""; echo "Done. Next: just setup"

# bootstrap: install uv if missing, create .venv, create .env, install dbt packages
[windows]
init: _init
    @Write-Host ""; Write-Host "Done. Next: just setup"

[unix]
[private]
_init:
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
    uv sync --all-groups
    # An installed git hook also carries the venv path; refresh it in the same case.
    if [ -f .git/hooks/pre-commit ]; then uv run pre-commit install >/dev/null; fi
    if [ ! -f .env ]; then cp .env.example .env && echo "created .env from .env.example"; fi
    mkdir -p .dagster .dlt/data
    uv run python scripts/dbt_all.py deps --quiet
    if command -v direnv >/dev/null 2>&1; then direnv allow . >/dev/null 2>&1 || true; fi

[windows]
[private]
_init:
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" }
    if ((Test-Path .venv\Scripts\activate.bat) -and -not (Select-String -Path .venv\Scripts\activate.bat -SimpleMatch "$PWD\.venv`"" -Quiet)) { if (Get-Process | Where-Object { $_.Path -like "$PWD\.venv\*" }) { Write-Host "checkout moved since .venv was created, but programs still run from it (Dagster?); stop them (just stop) and rerun"; exit 1 }; Write-Host "checkout moved since .venv was created, recreating it"; Remove-Item -Recurse -Force .venv }
    uv sync --all-groups
    if (Test-Path .git\hooks\pre-commit) { uv run pre-commit install | Out-Null }
    if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "created .env from .env.example" }
    New-Item -ItemType Directory -Force -Path .dagster, .dlt\data | Out-Null
    uv run python scripts/dbt_all.py deps --quiet

# everything in one go: `just init`, then the wizard (fresh account -> bootstrap incl. Terraform install; provisioned -> key pair + .env)
setup: _init
    uv run python scripts/snowflake.py wizard

# show tool versions and whether .env and your key pair are in place
info:
    uv run python scripts/info.py

# install a tool uv does not manage: all | uv | tfenv | terraform | direnv (Homebrew on macOS/Linux); `gh` is optional and not part of `all`
[unix]
install tool="all":
    #!/usr/bin/env bash
    set -euo pipefail
    brew_install() { if command -v brew >/dev/null 2>&1; then brew list "$1" >/dev/null 2>&1 && echo "$1 already installed" || brew install "$1"; else echo "Homebrew not found; install $1 by hand: $2"; fi; }
    case "{{tool}}" in
        uv)        command -v uv >/dev/null 2>&1 && echo "uv already installed" || curl -LsSf https://astral.sh/uv/install.sh | sh ;;
        tfenv)     brew_install tfenv https://github.com/tfutils/tfenv ;;
        tf|terraform)
                   command -v tfenv >/dev/null 2>&1 || brew_install tfenv https://github.com/tfutils/tfenv
                   tfenv install latest && tfenv use latest ;;
        direnv)    brew_install direnv https://direnv.net/docs/installation.html
                   echo 'then add to ~/.zshrc (or ~/.bashrc): eval "$(direnv hook zsh)"' ;;
        gh)        brew_install gh https://cli.github.com/
                   echo "then: gh auth login" ;;
        all)       for t in uv terraform direnv; do just install "$t"; done ;;
        *)         echo "usage: just install [all|uv|tfenv|terraform|direnv|gh]"; exit 1 ;;
    esac

# install a tool uv does not manage: all | uv | terraform | direnv (winget); `gh` is optional and not part of `all`
[windows]
install tool="all":
    @switch ("{{tool}}") { "uv" { if (Get-Command uv -ErrorAction SilentlyContinue) { "uv already installed" } else { powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" } } { $_ -in "tf", "terraform" } { winget install --id Hashicorp.Terraform -e } "direnv" { winget install --id direnv.direnv -e; Write-Host 'then add to $PROFILE: Invoke-Expression "$(direnv hook pwsh)"' } "gh" { winget install --id GitHub.cli -e; Write-Host "then: gh auth login" } "tfenv" { Write-Host "tfenv is not available on Windows; use: just install terraform" } "all" { just install uv; just install terraform; just install direnv } default { Write-Host "usage: just install [all|uv|terraform|direnv|gh]"; exit 1 } }

# --- Snowflake --------------------------------------------------------------

# Positional arguments keep a quoted SQL statement one argument instead of splitting it on spaces.

# key-pair auth: `just sf setup` (one-time), `bootstrap` (fresh account), `context` (pick a project), `check`, `query "SELECT 1"`, `keygen <name>`
[unix]
[positional-arguments]
sf cmd *args:
    uv run python scripts/snowflake.py "$@"

# key-pair auth: `just sf setup` (one-time), `bootstrap` (fresh account), `context` (pick a project), `check`, `query "SELECT 1"`, `keygen <name>`
[windows]
[positional-arguments]
[script("powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File")]
[extension(".ps1")]
sf cmd *args:
    uv run python scripts/snowflake.py @args
    exit $LASTEXITCODE

# --- Dagster ----------------------------------------------------------------

# start the Dagster dev server on http://localhost:3000 (Ctrl+C to stop); stops a previous instance first
[unix]
start: stop _dirs
    uv run dagster dev -w workspace.yaml -h 127.0.0.1 -p {{port}}

# Dagster captures a step's stdout/stderr (the run's stdout/stderr tabs) on Windows only with
# PYTHONLEGACYWINDOWSSTDIO set; its streams then use the console code page, so UTF-8 keeps
# non-ASCII output (dbt, dlt) from failing to encode.

# start the Dagster dev server on http://localhost:3000 (Ctrl+C to stop); stops a previous instance first
[windows]
start: stop _dirs
    $env:PYTHONLEGACYWINDOWSSTDIO = "1"; $env:PYTHONIOENCODING = "utf-8"; uv run dagster dev -w workspace.yaml -h 127.0.0.1 -p {{port}}

# stop the `dagster dev` instance on the Dagster port (webserver, daemon and code servers) and anything else on the port
[unix]
stop:
    #!/usr/bin/env bash
    # `dagster dev` shuts its daemon and code servers down on SIGTERM; a second instance would
    # otherwise fight the first one's daemon ("Another ... daemon is still sending heartbeats").
    if pkill -TERM -f "dagster dev -w workspace.yaml -h 127.0.0.1 -p {{port}}" 2>/dev/null; then
        echo "stopping dagster dev on port {{port}}"
        for _ in $(seq 1 20); do lsof -ti :{{port}} >/dev/null 2>&1 || break; sleep 0.5; done
    fi
    lsof -ti :{{port}} | xargs kill -9 2>/dev/null || true

# stop the `dagster dev` instance on the Dagster port (webserver, daemon and code servers) and anything else on the port
[windows]
stop:
    @Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like "*dagster dev -w workspace.yaml*-p {{port}}*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; $p = Get-NetTCPConnection -LocalPort {{port}} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 4 -and $_ -ne $PID }; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }; exit 0

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
    cd {{dbt_project}}; uv run sqlfluff {{args}} --config '{{sqlfluff_config}}'

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
    uv run --group docs zensical {{cmd}} {{args}}

# --- Quality ----------------------------------------------------------------

# format Python (ruff) and SQL (sqlfluff)
fmt:
    uv run ruff format .
    uv run ruff check --fix .
    cd {{dbt_project}}; uv run sqlfluff fix models --config '{{sqlfluff_config}}'

# lint Python and SQL without changing files
lint:
    uv run ruff check .
    uv run ruff format --check .
    cd {{dbt_project}}; uv run sqlfluff lint models --config '{{sqlfluff_config}}'

# type check Python with ty
typecheck:
    uv run ty check

# run the tests
test:
    uv run pytest

# everything CI runs: lint, typecheck, tests, dbt parse, Dagster definitions
check: lint typecheck test
    uv run python scripts/dbt_all.py parse --target dummy --quiet
    just validate
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
