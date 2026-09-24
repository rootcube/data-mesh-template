---
icon: material/console
---

# Commands

Everything runs through `just` (run it bare to list the recipes). Recipes are the same on
macOS, Linux and Windows; the few OS-specific ones have separate bodies in the `justfile`.
Every recipe loads `.env` and runs through `uv run`, so nothing needs activating.

## Setup

| Command | What it does |
|---------|--------------|
| `just setup` | Fresh account: `just init`, then `just snowflake bootstrap` (arguments pass through) |
| `just init` | Install uv if missing, `uv sync`, create `.env` from `.env.example`, create `.dagster/` and `.dlt/data/`, `dbt deps` in every project |
| `just info` | Tool and package versions, `.env` and private key status, what to run next |

## Snowflake

| Command | What it does |
|---------|--------------|
| `just snowflake bootstrap` | Fresh account, as `ACCOUNTADMIN` with a password: Terraform user and `init.sql`, your key pair, `config/users/<you>.yaml`, `TF_VAR_*` in `.env`, `terraform apply`, then the same context discovery and `.env` as `setup` (`--yes` auto-approves the plan) |
| `just snowflake setup` | One-time interactive login, key pair, registration on your user, verification, `.env` |
| `just snowflake setup --auth password` | Same, with password + MFA in the terminal instead of the browser |
| `just snowflake context` | Pick the project you work in from the roles granted to you, then write role, warehouse, database and schema prefix to `.env`; no login needed (`--role`, `--yes`) |
| `just snowflake setup --passphrase` | Encrypt the private key with a passphrase |
| `just snowflake setup --slot 2` | Register into `RSA_PUBLIC_KEY_2` (key rotation) |
| `just snowflake setup --account <org>-<account> --user <login> --yes` | Skip the prompts and keep every default |
| `just snowflake check` | Connect with the key pair and print your context plus the layer schemas |
| `just snowflake query "SELECT 1"` | Run one statement (`--limit 50` rows by default) |
| `just snowflake keygen <name>` | Key pair only, no login (service users, the Terraform user); `--force` overwrites |

## Dagster

| Command | What it does |
|---------|--------------|
| `just start` | `dagster dev -w workspace.yaml` on <http://localhost:3000>, foreground; runs `just stop` first so a forgotten instance never doubles the daemon |
| `just port=3001 start` | Same on another port |
| `just stop` | Stop the `dagster dev` instance on the Dagster port (webserver, daemon, code servers), then anything else still on the port |
| `just dagster <args>` | The Dagster CLI, e.g. `just dagster asset list -m orchestrator.locations.dlt.definitions` |
| `just validate` | Load every code location like `start` does, without the UI |

## dlt

| Command | What it does |
|---------|--------------|
| `just dlt list` | The ingest pipelines under `dlt_pipelines/pipelines/ingest/` |
| `just dlt run <source>` | Run one pipeline outside Dagster, e.g. `just dlt run knmi` |
| `just dlt run <source> --full-refresh` | Drop the source's tables and state in the destination, then load |

## dbt

| Command | What it does |
|---------|--------------|
| `just dbt <args>` | dbt in `dbt/dbt_example`, e.g. `just dbt build`, `just dbt parse` |
| `just project=dbt_x dbt <args>` | Same, in another project under `dbt/` |
| `just dbt-all <args>` | One dbt command in every project, e.g. `just dbt-all deps`, `just dbt-all parse --target dummy` |
| `just sqlfluff <args>` | sqlfluff from the project directory, e.g. `just sqlfluff lint models` |

## Terraform (platform administrators)

| Command | What it does |
|---------|--------------|
| `just tf <cmd> <args>` | Terraform in `terraform/`: `just tf init`, `just tf plan`, `just tf apply`, `just tf destroy` |
| `just tf output -json initial_passwords` | One-time passwords of persons Terraform created |
| `just tf output -json user_role_grants` | Roles per login |
| `just tf-validate-config` | Validate the YAML under `terraform/config/` against its JSON schemas and cross references |

## Docs

| Command | What it does |
|---------|--------------|
| `just docs` | Serve this site on <http://localhost:8000> |
| `just docs build --strict` | Build `site/` and fail on broken links (what CI runs) |

## Quality

| Command | What it does |
|---------|--------------|
| `just fmt` | `ruff format`, `ruff check --fix`, `sqlfluff fix models` |
| `just lint` | ruff and sqlfluff, no changes |
| `just typecheck` | ty |
| `just test` | pytest (offline) |
| `just check` | lint + typecheck + test, then `dbt parse` in every project with the dummy target, Dagster definitions validate and the Terraform config validation |
| `just pre-commit` | Run all pre-commit hooks on all files |
| `just pre-commit-install` | Install the git hook |

`just check` mirrors the CI workflow (`.github/workflows/ci.yml`): the jobs there are Python
(ruff, ty, pytest), dbt parse + Dagster definitions, Terraform fmt + validate + config
validation, and the docs build.

## Variables

Two `justfile` variables can be set on the command line, before the recipe name:

| Variable | Default | Used by |
|----------|---------|---------|
| `project` | `dbt_example` | `dbt`, `sqlfluff`, `fmt`, `lint` (the project directory under `dbt/`) |
| `port` | `3000` | `start`, `stop` |
