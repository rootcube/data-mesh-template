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
| `just setup` | `just init`, then one question: fresh account runs `just sf bootstrap` (installing Terraform and Atmos first if missing), provisioned account runs `just sf setup`, an account provisioned from another checkout runs `just sf bootstrap --existing ask --account-settings skip`, local only (no Snowflake) runs `just sf local`. It asks again for any answer that is not 1, 2, 3 or 4 |
| `just init` | Install uv if missing, `uv sync --all-groups`, create `.env` from `.env.example`, create `.dagster/`, `.dlt/data/` and `.duckdb/data/`, `dbt deps` and `dbt parse` in every project |
| `just info` | Tool and package versions, `.env` and private key status, what to run next, the local state folders and the installed packages of every dbt project, and one line per key `.env.example` sets that your `.env` misses (or the other way round) |
| `just reset-local` | Delete the git-ignored local state (`.dagster/` except `dagster.yaml`, `.dlt/data/`, `src/orchestrator/defs/.local_defs_state/`, `dbt/*/target/`, `dbt/*/logs/`, `logs/`, `.cache/`), recreate `.dagster/` and `.dlt/data/`, then `dbt deps` and `dbt parse` in every project. Stop `just start` first |
| `just install [tool]` | Install a tool uv does not manage: `uv`, `terraform` (tfenv on macOS and Linux), `atmos` (Homebrew on macOS and Linux; on Windows Scoop, or else the release the justfile pins, checked against its checksums, into `~\.local\bin`), `direnv`, or `all` (the default); `k3d` and `kubectl` for the local Kubernetes cluster, and `gh`, are available too but not part of `all` |

## Snowflake

| Command | What it does |
|---------|--------------|
| `just sf bootstrap` | Fresh account, as `ACCOUNTADMIN` with a password: the account parameters of `account_settings.sql` (listed, then applied if you confirm: `--account-settings ask|apply|skip`, default `ask`; `--yes` applies), the Terraform user's key pair (a passphrase prompt; empty for none) and `init.sql` (Terraform user, system roles, the trial defaults `COMPUTE_WH`, `SNOWFLAKE_LEARNING_*` and `SNOWFLAKE_SAMPLE_DATA` dropped), your own key pair (always asks for a passphrase, since this login holds `ACCOUNTADMIN`), `config/users/local/<you>.yaml` (git-ignored), `TF_VAR_*` in `.env`, `terraform apply` of every stack, the `account` stack first (your personal schemas included), then the same context discovery and `.env` as `setup` (`--yes` auto-approves the plans). Objects that already exist are adopted into the state of the stack that plans them and handed to their `SYSADMIN`, `SECURITYADMIN` or `USERADMIN` owner, or dropped first (`--existing ask|sync|wipe`, default `ask`; `--yes` picks sync). Objects a stack's state already tracks but another role owns (`ACCOUNTADMIN`, on an account an earlier version provisioned) are handed back to that owner before the plans, after you confirm (`--yes` does it). Grants a state tracks that the account no longer has, and that the plan would revoke, are removed from that state first: the provider cannot revoke a grant that has no privileges left. A key slot that already holds a different key is replaced only when you confirm |
| `just sf setup` | One-time interactive login, key pair, registration on your user, verification, `.env`: role, warehouse and database from the project roles granted to you, the schema prefix in `dev` (asked again until it is valid). A new key replaces the old files only once Snowflake accepted it (the old ones stay as `.bak`); a slot holding another key is replaced only when you confirm (yes by default when it is the key you are rotating away from, no when the key is unexpected); `.env` and the private key are readable by you only |
| `just sf setup --auth password` | Same, with password + MFA in the terminal instead of the browser |
| `just sf context` | Pick the project you work in from the roles granted to you, then write role, warehouse, database and schema prefix to `.env`; no login needed (`--role`, `--yes`). Roles outside `dev` are marked in the list and need an explicit confirmation, since runs from this checkout would then write to the shared `_<LAYER>` schemas; with `--yes` the warning is printed and the run continues |
| `just sf setup --passphrase` | Encrypt the private key with a passphrase |
| `just sf setup --slot 2` | Register into `RSA_PUBLIC_KEY_2` (key rotation) |
| `just sf setup --account <org>-<account> --user <login> --yes` | Skip the prompts and keep every default |
| `just sf check` | Connect with the key pair and print your context plus the layer schemas |
| `just sf query "SELECT 1"` | Run one statement and print the rows; at most 50 of them unless you pass `--limit` |
| `just sf keygen <name>` | Key pair only, no login (service users, the Terraform user), printed for `ALTER USER ... SET RSA_PUBLIC_KEY`; `--force` replaces an existing pair and keeps it as `.p8.bak` and `.pub.bak` (Snowflake still holds its public key until you register the new one), `--passphrase` encrypts the private key |
| `just sf local` | No Snowflake account at all: writes `ENVIRONMENT=local` to `.env`, nothing else. dlt and dbt then build against the DuckDB file `DUCKDB_PATH` points at. Same as `just setup` option 4 |

## Dagster

| Command | What it does |
|---------|--------------|
| `just start` | `dagster dev -w workspace.yaml` on <http://localhost:3000>, foreground; runs `just stop` first so a forgotten instance never doubles the daemon |
| `just port=3001 start` | Same on another port |
| `just stop` | Stop the `dagster dev` instance on the Dagster port (webserver, daemon, code servers) and wait for the port to come free; another program on the port is reported, not killed |
| `just dagster <args>` | The Dagster CLI, e.g. `just dagster asset list -m orchestrator.locations.dlt.definitions` or `just dagster job list -m orchestrator.locations.dlt.definitions` |
| `just validate` | Load every code location like `start` does, without the UI, then check that the dlt and dbt asset keys still match |

## dlt

| Command | What it does |
|---------|--------------|
| `just dlt list` | The ingest pipelines under `dlt_pipelines/pipelines/ingest/` |
| `just dlt run <source>` | Run one pipeline outside Dagster, e.g. `just dlt run knmi` |
| `just dlt run <source> --full-refresh` | Drop the source's tables and state in the destination, then load |

## dbt

| Command | What it does |
|---------|--------------|
| `just dbt <args>` | dbt in `dbt/dbt_example`, e.g. `just dbt build`, `just dbt parse`, `just dbt source freshness` |
| `just project=dbt_x dbt <args>` | Same, in another project under `dbt/` |
| `just dbt-all <args>` | One dbt command in every project, e.g. `just dbt-all deps`, `just dbt-all parse --target local` |
| `just sqlfluff <args>` | sqlfluff from the project directory, e.g. `just sqlfluff lint models` |

## Terraform (platform administrators)

| Command | What it does |
|---------|--------------|
| `just tf <cmd> <args>` | `atmos terraform <cmd> <args>`: Terraform once per stack, each with its own state (see [Stacks and state](../operate/snowflake-provisioning.md#stacks-and-state)). `just tf plan --all` and `just tf apply --all` run every stack, the `account` stack first; `just tf plan snowflake-project -s example-dev` runs one project in one environment; flags after `--` go to Terraform. `just tf destroy` is refused while the databases carry `prevent_destroy` |
| `just tf clean` | Remove every object the stacks' Terraform states track, databases and their data included. It lists them and asks you to type the account name, then stack by stack (the `account` stack last) has Terraform destroy the rest, drops the databases as `TERRAFORM_USER` and removes them from the state last, then names what stays: the `init.sql` objects (`TERRAFORM_USER` with its system roles and key, `WH_PLATFORM_PROVISIONING`) and the account parameters, with the SQL to drop or unset them. `just tf apply --all` provisions everything again. States that track nothing are reported as an error, not as success: the account may still be provisioned, and `just sf bootstrap --existing sync` adopts it |
| `just tf output snowflake-account -s account -- -json initial_passwords` | One-time passwords of persons Terraform created |
| `just tf output snowflake-account -s account -- -json user_role_grants` | Roles per login, over every project and environment |
| `just tf output snowflake-project -s <project>-dev -- -json personal_schemas` | Personal schemas per login in that project |
| `just tf-validate-config` | Validate the YAML under `terraform/config/` (sub-folders included) against its JSON schemas and cross references: a project's `code` equals its file name, users name existing projects, roles and environments, no two user files share a name, and there is one stack manifest `terraform/stacks/projects/<project>/<env>.yaml` per project and enabled environment |
| `just tf-split-state` | One-off: split a checkout's pre-Atmos `terraform/terraform.tfstate` into one state per stack, keeping the original as `terraform.tfstate.pre-atmos`; `--dry-run` shows where everything goes |

## Kubernetes (local k3d)

Dagster deployed to a local k3d cluster, one stack `dagster-<env>` per environment
([Dagster on Kubernetes](../operate/kubernetes.md)). A Docker engine must be running; `stack`
defaults to `dagster-prd`.

| Command | What it does |
|---------|--------------|
| `just k8s up` | Create the k3d cluster `dagster` (kube context `k3d-dagster`), or start it when it exists |
| `just k8s build` | `docker build` of the code location image `dagster-starter:local`, imported into the cluster |
| `just k8s deploy [stack]` | `build`, then `atmos terraform apply dagster -s <stack>` (you confirm), then a restart of the code servers so they run the new build |
| `just k8s ui [stack]` | Forward the webserver to <http://localhost:3000> until Ctrl+C |
| `just k8s down` | Stop the cluster; everything in it stays, run history included |

## Docs

| Command | What it does |
|---------|--------------|
| `just docs` | Serve this site on <http://localhost:8000> |
| `just docs build --strict` | Build `site/` and fail on a broken link or anchor. CI runs `scripts/check_doc_fences.py` first, as `just check` does |

## Quality

| Command | What it does |
|---------|--------------|
| `just fmt` | `ruff format`, `ruff check --fix`, `sqlfluff fix models` |
| `just lint` | ruff and sqlfluff, no changes |
| `just typecheck` | ty |
| `just test` | pytest (offline) |
| `just check` | lint + typecheck + test, then `dbt parse` in every project with the local target (on both parsers), `just validate`, the Terraform config validation, the docs fence check and `just docs build --strict` |
| `just pre-commit` | Run all pre-commit hooks on all files |
| `just pre-commit-install` | Install the git hook |

`just check` is everything CI runs apart from the Terraform and Atmos CLI steps and the fresh-machine
`setup` matrix. The hooks and jobs one by one:
[What runs when](git-workflow.md#what-runs-when).

## Variables

Two `justfile` variables can be set on the command line, before the recipe name:

| Variable | Default | Used by |
|----------|---------|---------|
| `project` | `dbt_example` | `dbt`, `sqlfluff`, `fmt`, `lint` (the project directory under `dbt/`) |
| `port` | `3000` | `start`, `stop` |
