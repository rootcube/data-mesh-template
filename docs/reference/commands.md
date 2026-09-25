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
| `just setup` | `just init`, then one question: fresh account runs `just sf bootstrap` (installing Terraform first if missing), provisioned account runs `just sf setup`, an account provisioned from another checkout runs `just sf bootstrap --existing ask --account-settings skip` |
| `just init` | Install uv if missing, `uv sync --all-groups`, create `.env` from `.env.example`, create `.dagster/` and `.dlt/data/`, `dbt deps` in every project |
| `just info` | Tool and package versions, `.env` and private key status, what to run next |
| `just install [tool]` | Install a tool uv does not manage: `uv`, `terraform` (tfenv on macOS and Linux), `direnv`, or `all` (the default); `gh` is available too but optional, nothing in the repo needs it |

## Snowflake

| Command | What it does |
|---------|--------------|
| `just sf bootstrap` | Fresh account, as `ACCOUNTADMIN` with a password: the account parameters of `account_settings.sql` (listed, then applied if you confirm: `--account-settings ask|apply|skip`, default `ask`; `--yes` applies), the Terraform user's key pair (a passphrase prompt; empty for none) and `init.sql` (Terraform user, system roles), your own key pair (always asks for a passphrase, since this login holds `ACCOUNTADMIN`), `config/users/local/<you>.yaml` (git-ignored), `TF_VAR_*` in `.env`, `terraform apply` (your personal schemas included), then the same context discovery and `.env` as `setup` (`--yes` auto-approves the plan). Objects that already exist are adopted into the state and handed to their `SYSADMIN`, `SECURITYADMIN` or `USERADMIN` owner, or dropped first (`--existing ask|sync|wipe`, default `ask`; `--yes` picks sync). A key slot that already holds a different key is replaced only when you confirm |
| `just sf setup` | One-time interactive login, key pair, registration on your user, verification, `.env`: role, warehouse and database from the project roles granted to you, the schema prefix in `dev` (asked again until it is valid). A new key replaces the old files only once Snowflake accepted it (the old ones stay as `.bak`); a slot holding another key is replaced only when you confirm; `.env` and the private key are readable by you only |
| `just sf setup --auth password` | Same, with password + MFA in the terminal instead of the browser |
| `just sf context` | Pick the project you work in from the roles granted to you, then write role, warehouse, database and schema prefix to `.env`; no login needed (`--role`, `--yes`) |
| `just sf setup --passphrase` | Encrypt the private key with a passphrase |
| `just sf setup --slot 2` | Register into `RSA_PUBLIC_KEY_2` (key rotation) |
| `just sf setup --account <org>-<account> --user <login> --yes` | Skip the prompts and keep every default |
| `just sf check` | Connect with the key pair and print your context plus the layer schemas |
| `just sf query "SELECT 1"` | Run one statement (`--limit 50` rows by default) |
| `just sf keygen <name>` | Key pair only, no login (service users, the Terraform user), printed for `ALTER USER ... SET RSA_PUBLIC_KEY`; `--force` overwrites, `--passphrase` encrypts the private key |

## Dagster

| Command | What it does |
|---------|--------------|
| `just start` | `dagster dev -w workspace.yaml` on <http://localhost:3000>, foreground; runs `just stop` first so a forgotten instance never doubles the daemon |
| `just port=3001 start` | Same on another port |
| `just stop` | Stop the `dagster dev` instance on the Dagster port (webserver, daemon, code servers), then anything else still listening on the port |
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
| `just tf <cmd> <args>` | Terraform in `terraform/`: `just tf init`, `just tf plan`, `just tf apply`, `just tf destroy` (refused while the databases carry `prevent_destroy`; see [State and teardown](../administration/snowflake-provisioning.md#state-and-teardown)) |
| `just tf output -json initial_passwords` | One-time passwords of persons Terraform created |
| `just tf output -json user_role_grants` | Roles per login |
| `just tf output -json personal_schemas` | Personal schemas per login |
| `just tf-validate-config` | Validate the YAML under `terraform/config/` (sub-folders included) against its JSON schemas and cross references: a project's `code` equals its file name, users name existing projects, roles and environments, no two user files share a name |

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
