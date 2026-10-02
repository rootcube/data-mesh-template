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
# Multi-line [windows] recipes carry [script] and run as one .ps1 file; a failing command does not
# stop such a script by itself, so they check $LASTEXITCODE. The [unix] recipes use a shebang.
set script-interpreter := ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]

# Local state lives inside the repo, so deleting .dagster/ (keep dagster.yaml), .dlt/data/ and .duckdb/ resets everything.
export DAGSTER_HOME     := justfile_directory() / ".dagster"
export DLT_PROJECT_DIR  := justfile_directory()
export DLT_DATA_DIR     := justfile_directory() / ".dlt" / "data"
export DBT_PROFILES_DIR := justfile_directory() / "dbt"
# The DuckDB file behind the `local` dbt target and the local dlt destination (ENVIRONMENT=local).
export DUCKDB_PATH      := justfile_directory() / ".duckdb" / "data" / "local.duckdb"
# The Snowflake connector's vendored requests warns about urllib3 on every command; nothing to fix here.
export PYTHONWARNINGS := "ignore:::snowflake.connector.vendored.requests"
# uv's installer puts it in ~/.local/bin; each recipe line is a fresh shell, so make it findable
# right after `just init` installs it, before the user restarts their shell.
_uv_bin   := if os_family() == "windows" { home_directory() + "\\.local\\bin" } else { home_directory() / ".local" / "bin" }
_path_sep := if os_family() == "windows" { ";" } else { ":" }
# Same for `just install terraform`, `k3d` and `kubectl` on Windows: winget adds each package folder
# to the user PATH (or links the tool into WinGet\Links when it may create symlinks), which only
# shells started after the install pick up.
_winget_pkg := env("LOCALAPPDATA", "") + "\\Microsoft\\WinGet\\Packages\\"
_winget_src := "_Microsoft.Winget.Source_8wekyb3d8bbwe" + _path_sep
_winget_bin := if os_family() == "windows" { env("LOCALAPPDATA", "") + "\\Microsoft\\WinGet\\Links" + _path_sep + _winget_pkg + "Hashicorp.Terraform" + _winget_src + _winget_pkg + "k3d.k3d" + _winget_src + _winget_pkg + "Kubernetes.kubectl" + _winget_src } else { "" }
export PATH := _uv_bin + _path_sep + _winget_bin + env("PATH")

# Overridable: `just project=dbt_other dbt build` targets another dbt project under dbt/.
project     := "dbt_example"
dbt_project := "dbt" / project
# The Atmos release `just install atmos` fetches on Windows (Homebrew installs its latest elsewhere);
# atmos.yaml states the versions this configuration works with.
atmos_version := "1.230.1"
# The local Kubernetes cluster (k3d) and the image `just k8s build` imports into it: the image of
# terraform/stacks/deployments/dagster/*.yaml, whose kube_context is k3d-<cluster>.
k8s_cluster := "dagster"
k8s_image   := "dagster-starter:local"
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
init: _init
    @echo ""; echo "Done. Next: just setup"

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
    mkdir -p .dagster .dlt/data .duckdb/data
    uv run python scripts/dbt_all.py deps --quiet
    uv run python scripts/dbt_all.py parse --target local --quiet
    if command -v direnv >/dev/null 2>&1; then direnv allow . >/dev/null 2>&1 || true; fi

[windows]
[private]
[script]
[extension(".ps1")]
_init:
    function Check { if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"; Check }
    # A moved or renamed checkout leaves .venv scripts pointing at the old path; rebuild it, unless
    # programs still run from it (Windows cannot delete their files).
    if ((Test-Path .venv\Scripts\activate.bat) -and -not (Select-String -Path .venv\Scripts\activate.bat -SimpleMatch "$PWD\.venv`"" -Quiet)) {
        if (Get-Process | Where-Object { $_.Path -like "$PWD\.venv\*" }) {
            Write-Host "checkout moved since .venv was created, but programs still run from it (Dagster?); stop them (just stop) and rerun"
            exit 1
        }
        Write-Host "checkout moved since .venv was created, recreating it"
        Remove-Item -Recurse -Force .venv
    }
    uv sync --all-groups; Check
    # An installed git hook also carries the venv path; refresh it in the same case.
    if (Test-Path .git\hooks\pre-commit) { uv run pre-commit install | Out-Null; Check }
    if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "created .env from .env.example" }
    New-Item -ItemType Directory -Force -Path .dagster, .dlt\data, .duckdb\data | Out-Null
    uv run python scripts/dbt_all.py deps --quiet; Check
    uv run python scripts/dbt_all.py parse --target local --quiet; Check

# everything in one go: `just init`, then the wizard (fresh account -> bootstrap incl. Terraform install; provisioned -> key pair + .env)
setup: _init
    uv run python scripts/snowflake.py wizard

# show tool versions and whether .env and your key pair are in place
info:
    uv run python scripts/info.py

# install a tool uv does not manage: all | uv | tfenv | terraform | atmos | direnv (Homebrew on macOS/Linux); `docker`, `k3d`, `kubectl` (local Kubernetes, `k8s` for all three) and `gh` are optional and not part of `all`
[unix]
install tool="all":
    #!/usr/bin/env bash
    set -euo pipefail
    brew_install() { if command -v brew >/dev/null 2>&1; then brew list "$1" >/dev/null 2>&1 && echo "$1 already installed" || brew install "$1"; else echo "Homebrew not found; install $1 by hand: $2"; return 1; fi; }
    case "{{tool}}" in
        uv)        command -v uv >/dev/null 2>&1 && echo "uv already installed" || curl -LsSf https://astral.sh/uv/install.sh | sh ;;
        tfenv)     brew_install tfenv https://github.com/tfutils/tfenv ;;
        tf|terraform)
                   if command -v terraform >/dev/null 2>&1; then echo "terraform already installed"; else
                       command -v tfenv >/dev/null 2>&1 || brew_install tfenv https://github.com/tfutils/tfenv
                       tfenv install latest && tfenv use latest; fi ;;
        atmos)     if command -v brew >/dev/null 2>&1 && brew list atmos >/dev/null 2>&1; then brew upgrade atmos; else brew_install atmos https://atmos.tools/install; fi ;;
        # Docker Desktop on macOS, as on Windows (the cask, not the `docker` formula, which is the CLI
        # alone): it ships buildx, which the Dockerfile's cache mounts need. A paid subscription from
        # 250 employees or $10M revenue. Linux runs Docker Engine itself, from the distribution.
        docker)    if command -v docker >/dev/null 2>&1; then echo "docker already installed"
                   elif [ "$(uname -s)" = Darwin ]; then brew_install docker-desktop https://docs.docker.com/desktop/
                       echo "then: start Docker Desktop once (accept its terms), and open a new terminal"
                   else echo "install Docker Engine by hand: https://docs.docker.com/engine/install/"; exit 1; fi ;;
        k3d)       brew_install k3d https://k3d.io ;;
        kubectl)   brew_install kubectl https://kubernetes.io/docs/tasks/tools/ ;;
        k8s)       for t in docker k3d kubectl; do just install "$t" || echo "$t: install by hand"; done ;;
        direnv)    brew_install direnv https://direnv.net/docs/installation.html
                   echo 'then add to ~/.zshrc (or ~/.bashrc): eval "$(direnv hook zsh)"' ;;
        gh)        brew_install gh https://cli.github.com/
                   echo "then: gh auth login" ;;
        all)       for t in uv terraform atmos direnv; do just install "$t" || echo "$t: install by hand"; done ;;
        *)         echo "usage: just install [all|uv|tfenv|terraform|atmos|docker|k3d|kubectl|k8s|direnv|gh]"; exit 1 ;;
    esac

# install a tool uv does not manage: all | uv | terraform | atmos | direnv (winget); `docker` (Docker Desktop), `k3d`, `kubectl` (local Kubernetes, `k8s` for all three) and `gh` are optional and not part of `all`
[windows]
[script]
[extension(".ps1")]
install tool="all":
    # winget's "no applicable upgrade": installed, but after this terminal started, so not on its PATH yet
    $upToDate = -1978335189
    function Install-Tool($command, $id) {
        if (Get-Command $command -ErrorAction SilentlyContinue) { "$command already installed"; return }
        winget install --id $id -e
        if ($LASTEXITCODE -eq $upToDate) { "$command already installed; open a new terminal to use it"; $global:LASTEXITCODE = 0 }
    }
    switch ("{{tool}}") {
        "uv"      { if (Get-Command uv -ErrorAction SilentlyContinue) { "uv already installed" } else { powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" } }
        { $_ -in "tf", "terraform" } { Install-Tool terraform Hashicorp.Terraform }
        "atmos"   { just _install-atmos }
        "docker"  {
            if (Get-Command docker -ErrorAction SilentlyContinue) { "docker already installed"; break }
            # Docker Desktop runs its engine in WSL2, whose install needs administrator rights and a reboot
            wsl --status *> $null
            if ($LASTEXITCODE -ne 0) { Write-Host "WSL2 first (Docker Desktop runs its engine in it): wsl --install --no-distribution in an administrator shell, reboot, then just install docker again"; exit 1 }
            Install-Tool docker Docker.DockerDesktop
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            Write-Host "then: start Docker Desktop once (accept its terms; sign out and in when it asks), and open a new terminal"
        }
        "k3d"     { Install-Tool k3d k3d.k3d }
        "kubectl" { Install-Tool kubectl Kubernetes.kubectl }
        "k8s"     { just install docker; just install k3d; just install kubectl }
        "direnv"  { Install-Tool direnv direnv.direnv; Write-Host 'then add to $PROFILE: Invoke-Expression "$(direnv hook pwsh)"' }
        "gh"      { Install-Tool gh GitHub.cli; Write-Host "then: gh auth login" }
        "tfenv"   { Write-Host "tfenv is not available on Windows; use: just install terraform" }
        "all"     { just install uv; just install terraform; just install atmos; just install direnv }
        default   { Write-Host "usage: just install [all|uv|terraform|atmos|docker|k3d|kubectl|k8s|direnv|gh]"; exit 1 }
    }
    exit $LASTEXITCODE

# Atmos has no winget package: Scoop when you have it, otherwise the release binary, checked against
# the release's SHA256SUMS, into ~\.local\bin (on PATH through uv's installer).
[windows]
[script]
[extension(".ps1")]
_install-atmos:
    $ErrorActionPreference = "Stop"; $ProgressPreference = "SilentlyContinue"
    if (Get-Command atmos -ErrorAction SilentlyContinue) { "atmos already installed"; exit 0 }
    if (Get-Command scoop -ErrorAction SilentlyContinue) { scoop install atmos; exit $LASTEXITCODE }
    $version = "{{atmos_version}}"
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "amd64" }
    $name = "atmos_${version}_windows_$arch.exe"
    $base = "https://github.com/cloudposse/atmos/releases/download/v$version"
    $download = Join-Path $env:TEMP $name
    $sums = Join-Path $env:TEMP "atmos_${version}_SHA256SUMS"
    Invoke-WebRequest "$base/$name" -OutFile $download
    Invoke-WebRequest "$base/atmos_${version}_SHA256SUMS" -OutFile $sums
    $expected = (Select-String -Path $sums -Pattern " $([regex]::Escape($name))$").Line.Split(" ")[0]
    if ((Get-FileHash $download -Algorithm SHA256).Hash -ne $expected.ToUpper()) { Remove-Item $download; throw "checksum mismatch for $name" }
    $bin = Join-Path $HOME ".local\bin"
    New-Item -ItemType Directory -Force $bin | Out-Null
    Move-Item -Force $download (Join-Path $bin "atmos.exe")
    Remove-Item $sums
    "atmos $version installed in $bin"

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
[script]
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

# stop the `dagster dev` instance on the Dagster port (webserver, daemon and code servers); another program on the port is reported, not killed
[unix]
stop:
    #!/usr/bin/env bash
    # `dagster dev` shuts its daemon and code servers down on SIGTERM; a second instance would
    # otherwise fight the first one's daemon ("Another ... daemon is still sending heartbeats").
    # Only listeners: a plain `lsof -i :port` also lists clients, such as a browser showing the UI.
    # lsof is missing on a bare Linux, and a failing `lsof` reads the same as a free port; connect
    # to it instead, so the wait below happens either way.
    listening() {
        if command -v lsof >/dev/null 2>&1; then
            lsof -ti tcp:{{port}} -sTCP:LISTEN >/dev/null 2>&1
        else
            uv run python -c "import socket, sys; sys.exit(socket.socket().connect_ex(('127.0.0.1', {{port}})) != 0)"
        fi
    }
    if pkill -TERM -f "dagster dev -w workspace.yaml -h 127.0.0.1 -p {{port}}" 2>/dev/null; then
        echo "stopping dagster dev on port {{port}}"
        for _ in $(seq 1 20); do listening || break; sleep 0.5; done
    fi
    # Still listening: a dagster process that ignored the SIGTERM, or something that is not ours.
    for pid in $(lsof -ti tcp:{{port}} -sTCP:LISTEN 2>/dev/null); do
        cmdline=$(ps -o command= -p "$pid" 2>/dev/null || true)
        case "$cmdline" in
            *dagster*) kill -9 "$pid" 2>/dev/null || true ;;
            *) echo "port {{port}} is in use by pid $pid: $cmdline"; exit 1 ;;
        esac
    done

# stop the `dagster dev` instance on the Dagster port (webserver, daemon and code servers); another program on the port is reported, not killed
[windows]
[script]
[extension(".ps1")]
stop:
    # The `dagster dev` processes of this port, by command line: webserver, daemon and code servers
    Get-CimInstance Win32_Process |
        Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like "*dagster dev -w workspace.yaml*-p {{port}}*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    # Still listening: a dagster process that survived, or something that is not ours
    $owners = Get-NetTCPConnection -LocalPort {{port}} -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -gt 4 -and $_ -ne $PID }
    foreach ($id in $owners) {
        $line = (Get-CimInstance Win32_Process -Filter "ProcessId = $id").CommandLine
        if ($line -like "*dagster*") { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; continue }
        Write-Host "port {{port}} is in use by pid $id`: $line"
        exit 1
    }
    exit 0

# run the Dagster CLI, e.g. `just dagster asset list -m orchestrator.locations.dlt.definitions`
[unix]
[positional-arguments]
dagster *args:
    uv run dagster "$@"

# run the Dagster CLI, e.g. `just dagster asset list -m orchestrator.locations.dlt.definitions`
[windows]
[positional-arguments]
[script]
[extension(".ps1")]
dagster *args:
    uv run dagster @args
    exit $LASTEXITCODE

# `dagster definitions validate` is superseded by `dg check defs`, which does not read workspace.yaml;
# PYTHONWARNINGS adds a filter for that one nag to the global one (the pre-commit hook runs this
# recipe; ci.yml sets the same filter).

# load every code location exactly like `just start` does, without the UI, then check that the dlt
# and dbt asset keys still line up (definitions validate loads each location on its own and cannot see that)
[unix]
validate:
    PYTHONWARNINGS='{{PYTHONWARNINGS}},ignore:Function `definitions_validate_command`' uv run dagster definitions validate -w workspace.yaml
    uv run python scripts/check_asset_keys.py

# load every code location exactly like `just start` does, without the UI, then check that the dlt
# and dbt asset keys still line up (definitions validate loads each location on its own and cannot see that)
[windows]
validate:
    $env:PYTHONWARNINGS = '{{PYTHONWARNINGS}},ignore:Function `definitions_validate_command`'; uv run dagster definitions validate -w workspace.yaml
    uv run python scripts/check_asset_keys.py

# --- dlt --------------------------------------------------------------------

# run a dlt pipeline outside Dagster: `just dlt list`, `just dlt run knmi`
[unix]
[positional-arguments]
dlt cmd *args: _dirs
    uv run python -m dlt_pipelines "$@"

# run a dlt pipeline outside Dagster: `just dlt list`, `just dlt run knmi`
[windows]
[positional-arguments]
[script]
[extension(".ps1")]
dlt cmd *args: _dirs
    uv run python -m dlt_pipelines @args
    exit $LASTEXITCODE

# --- dbt --------------------------------------------------------------------

# run dbt in dbt/dbt_example (override: `just project=dbt_x dbt build`), e.g. `just dbt build`
[unix]
[positional-arguments]
dbt *args:
    cd {{dbt_project}}; uv run dbt "$@"

# run dbt in dbt/dbt_example (override: `just project=dbt_x dbt build`), e.g. `just dbt build`
[windows]
[positional-arguments]
[script]
[extension(".ps1")]
dbt *args:
    cd {{dbt_project}}; uv run dbt @args
    exit $LASTEXITCODE

# run one dbt command in every project under dbt/, e.g. `just dbt-all deps`, `just dbt-all parse`
[unix]
[positional-arguments]
dbt-all *args:
    uv run python scripts/dbt_all.py "$@"

# run one dbt command in every project under dbt/, e.g. `just dbt-all deps`, `just dbt-all parse`
[windows]
[positional-arguments]
[script]
[extension(".ps1")]
dbt-all *args:
    uv run python scripts/dbt_all.py @args
    exit $LASTEXITCODE

# lint or fix SQL with sqlfluff from the dbt project, e.g. `just sqlfluff lint models`
[unix]
[positional-arguments]
sqlfluff *args:
    cd {{dbt_project}}; uv run sqlfluff "$@" --config '{{sqlfluff_config}}'

# lint or fix SQL with sqlfluff from the dbt project, e.g. `just sqlfluff lint models`
[windows]
[positional-arguments]
[script]
[extension(".ps1")]
sqlfluff *args:
    cd {{dbt_project}}; uv run sqlfluff @args --config '{{sqlfluff_config}}'
    exit $LASTEXITCODE

# --- Terraform (platform administrators) -----------------------------------

# run Terraform through Atmos on the stacks, e.g. `just tf plan --all` (the Snowflake stacks; a Dagster deployment has `just k8s deploy`), `just tf plan snowflake-project -s example-dev`, `just tf apply --all`; `just tf clean` removes every object the stacks' states track, databases and their data included
[unix]
[positional-arguments]
tf cmd *args:
    #!/usr/bin/env bash
    set -euo pipefail
    # `--all` is every stack that provisions Snowflake. A deployment (a stack under
    # terraform/stacks/deployments/, which sets `vars.deployment`) needs its cluster: `just k8s deploy`.
    if [ "$1" = clean ]; then
        uv run python scripts/snowflake.py clean
    elif [[ " $* " == *" --all "* ]]; then
        cmd="$1"; shift
        atmos terraform "$cmd" --query '.vars.deployment == null' "$@"
    else
        atmos terraform "$@"
    fi

# run Terraform through Atmos on the stacks, e.g. `just tf plan --all` (the Snowflake stacks; a Dagster deployment has `just k8s deploy`), `just tf plan snowflake-project -s example-dev`, `just tf apply --all`; `just tf clean` removes every object the stacks' states track, databases and their data included
[windows]
[positional-arguments]
[script]
[extension(".ps1")]
tf cmd *args:
    # `--all` is every stack that provisions Snowflake. A deployment (a stack under
    # terraform/stacks/deployments/, which sets `vars.deployment`) needs its cluster: `just k8s deploy`.
    if ($args[0] -eq "clean") { uv run python scripts/snowflake.py clean }
    elseif ($args -contains "--all") { $rest = @($args | Select-Object -Skip 1); atmos terraform $args[0] --query '.vars.deployment == null' @rest }
    else { atmos terraform @args }
    exit $LASTEXITCODE

# validate the YAML configuration under terraform/config against its JSON schemas
tf-validate-config:
    uv run python terraform/config/_validation/validate_configs.py

# --- Kubernetes (local k3d) ------------------------------------------------
# The Dagster deployment of a stack terraform/stacks/deployments/dagster/<env>.yaml; its namespace
# is the stack name (<deployment>-<env>). A Docker engine must be running (docs/operate/kubernetes.md).

# local Kubernetes for Dagster: `just k8s up` (create or start the k3d cluster), `build` (image into the cluster), `deploy [stack]` (build + apply + restart), `ui [stack]` (webserver on :3000), `down`
[unix]
k8s cmd stack="dagster-prd":
    #!/usr/bin/env bash
    set -euo pipefail
    context="k3d-{{k8s_cluster}}"
    case "{{cmd}}" in
        up)     if k3d cluster get {{k8s_cluster}} >/dev/null 2>&1; then k3d cluster start {{k8s_cluster}}; else k3d cluster create {{k8s_cluster}} --wait; fi ;;
        build)  docker build -t {{k8s_image}} .
                k3d image import {{k8s_image}} -c {{k8s_cluster}} ;;
        # The image keeps its tag, so the running code servers only pick up a new build on a restart.
        deploy) just k8s build
                atmos terraform apply dagster -s {{stack}}
                kubectl --context "$context" -n {{stack}} rollout restart deployment ;;
        ui)     pod=$(kubectl --context "$context" -n {{stack}} get pods -l component=dagster-webserver -o jsonpath='{.items[0].metadata.name}')
                echo "Dagster on http://localhost:3000 (Ctrl+C stops the forward)"
                kubectl --context "$context" -n {{stack}} port-forward "$pod" 3000:80 ;;
        down)   k3d cluster stop {{k8s_cluster}} ;;
        *)      echo "usage: just k8s up|build|deploy|ui|down [stack]"; exit 1 ;;
    esac

# local Kubernetes for Dagster: `just k8s up` (create or start the k3d cluster), `build` (image into the cluster), `deploy [stack]` (build + apply + restart), `ui [stack]` (webserver on :3000), `down`
[windows]
[script]
[extension(".ps1")]
k8s cmd stack="dagster-prd":
    $context = "k3d-{{k8s_cluster}}"
    function Check { if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
    switch ("{{cmd}}") {
        "up" {
            k3d cluster get {{k8s_cluster}} *> $null
            if ($LASTEXITCODE -eq 0) { k3d cluster start {{k8s_cluster}} } else { k3d cluster create {{k8s_cluster}} --wait }; Check
        }
        "build" { docker build -t {{k8s_image}} .; Check; k3d image import {{k8s_image}} -c {{k8s_cluster}}; Check }
        # The image keeps its tag, so the running code servers only pick up a new build on a restart.
        "deploy" {
            just k8s build; Check
            atmos terraform apply dagster -s {{stack}}; Check
            kubectl --context $context -n {{stack}} rollout restart deployment; Check
        }
        "ui" {
            $pod = kubectl --context $context -n {{stack}} get pods -l component=dagster-webserver -o "jsonpath={.items[0].metadata.name}"; Check
            Write-Host "Dagster on http://localhost:3000 (Ctrl+C stops the forward)"
            kubectl --context $context -n {{stack}} port-forward $pod 3000:80
        }
        "down" { k3d cluster stop {{k8s_cluster}}; Check }
        default { Write-Host "usage: just k8s up|build|deploy|ui|down [stack]"; exit 1 }
    }
    exit $LASTEXITCODE

# --- Docs -------------------------------------------------------------------

# serve the docs on http://localhost:8000 (`just docs build` for a static site/)
[unix]
[positional-arguments]
docs cmd="serve" *args:
    uv run --group docs zensical "$@"

# serve the docs on http://localhost:8000 (`just docs build` for a static site/)
[windows]
[positional-arguments]
[script]
[extension(".ps1")]
docs cmd="serve" *args:
    uv run --group docs zensical @args
    exit $LASTEXITCODE

# --- Quality ----------------------------------------------------------------

# format Python (ruff) and SQL (sqlfluff, every project under dbt/)
fmt:
    uv run ruff check --fix .
    uv run ruff format .
    just sqlfluff fix models
    just project=dbt_common sqlfluff fix models

# lint Python and SQL (every project under dbt/) without changing files
lint:
    uv run ruff check .
    uv run ruff format --check .
    just sqlfluff lint models
    just project=dbt_common sqlfluff lint models

# type check Python with ty
typecheck:
    uv run ty check

# run the tests
test:
    uv run pytest

# what CI runs apart from the Terraform CLI checks: lint, typecheck, tests, dbt parse (dbt 1.x and the v2 parser), Dagster definitions, the config schemas, the docs build
check: lint typecheck test
    uv run python scripts/dbt_all.py parse --target local --quiet
    uv run python scripts/dbt_all.py parse --target local --quiet --use-v2-parser
    just validate
    uv run python terraform/config/_validation/validate_configs.py
    uv run python scripts/check_doc_fences.py
    just docs build --strict

# run all pre-commit hooks on all files
pre-commit:
    uv run pre-commit run --all-files

# install the git pre-commit hook
pre-commit-install:
    uv run pre-commit install

# --- Private helpers --------------------------------------------------------

[private]
_dirs:
    @uv run python -c "import pathlib; [pathlib.Path(p).mkdir(parents=True, exist_ok=True) for p in ('.dagster', '.dlt/data', '.duckdb/data')]"

# --- Local state ------------------------------------------------------------

# delete the git-ignored local state (run history, dlt data, the local DuckDB file, component cache, dbt target/logs, docs cache), then dbt deps + parse; stop `just start` first
[unix]
reset-local:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -d .dagster ]; then find .dagster -mindepth 1 -maxdepth 1 ! -name dagster.yaml -exec rm -rf {} +; fi
    rm -rf .dlt/data .duckdb src/orchestrator/defs/.local_defs_state dbt/*/target dbt/*/logs logs .cache
    mkdir -p .dagster .dlt/data .duckdb/data
    uv run python scripts/dbt_all.py deps --quiet
    uv run python scripts/dbt_all.py parse --target local --quiet
    echo "local state reset"

# delete the git-ignored local state (run history, dlt data, the local DuckDB file, component cache, dbt target/logs, docs cache), then dbt deps + parse; stop `just start` first
[windows]
reset-local:
    @Get-ChildItem .dagster -Exclude dagster.yaml -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    @Remove-Item -Path .dlt\data, .duckdb, src\orchestrator\defs\.local_defs_state, dbt\*\target, dbt\*\logs, logs, .cache -Recurse -Force -ErrorAction SilentlyContinue
    @New-Item -ItemType Directory -Force -Path .dagster, .dlt\data, .duckdb\data | Out-Null
    uv run python scripts/dbt_all.py deps --quiet
    uv run python scripts/dbt_all.py parse --target local --quiet
    @Write-Host "local state reset"
