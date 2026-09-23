---
icon: material/shield-check
---

# Standards and quality

Every rule in this repo is enforced by a tool: pre-commit hooks locally, GitHub Actions on every push to `main` and every pull request. This page is the agent-facing map of that enforcement chain: how to run the checks yourself, where each rule canonically lives, and what to do when a check fails. The rules themselves are documented on the linked pages, not restated here; `AGENTS.md` remains the canonical instruction set.

## Run the checks

Run the validation loop and make it pass before presenting any work (a hard rule from `AGENTS.md`):

```bash
just fmt                # ruff format + ruff check --fix + sqlfluff fix (active dbt project)
just typecheck          # ty check
just test               # pytest
just validate           # dagster definitions validate -w workspace.yaml
just check              # everything CI runs: lint, typecheck, test, dbt parse (dummy), validate, Terraform YAML
just pre-commit         # the full hook chain, on all files
```

`just lint` is the read-only twin of `just fmt` (`ruff check`, `ruff format --check`, `sqlfluff lint`); CI runs that form. Two more checks belong to specific files: `just tf-validate-config` for the YAML under `terraform/config/` and `just docs build --strict` for anything under `docs/`.

!!! note "`just fmt` formats SQL in one project only"
    The Python part covers the whole repo (`ruff format .` and `ruff check --fix .`, with `dbt/`, `terraform/`, `site/` and `docs/` excluded in `pyproject.toml`). The `sqlfluff fix models` part runs inside the active dbt project, `dbt/dbt_example` by default. For another project: `just project=dbt_x fmt`.

Every recipe with every flag: [Command reference](../reference/commands.md).

## The enforcement chain

Two layers run the same checks.

### 1. Pre-commit hooks

Installed once with `just pre-commit-install`, they fire on every `git commit` (humans commit; agents run `just pre-commit` instead). `.pre-commit-config.yaml` is the ground truth. In execution order:

| Hook | What it does | Fires on |
|---|---|---|
| `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-merge-conflict`, `detect-private-key` | The standard pre-commit hygiene hooks; `check-yaml` runs with `--unsafe` because dbt YAML carries `{{ env_var() }}` and `defs.yaml` carries templates | Every file |
| `ruff format`, `ruff check --fix` | Python formatting and lint | `*.py` |
| `ty check` | Whole-project type check | Any `*.py` change |
| `dbt parse` | `scripts/dbt_all.py parse --target dummy --quiet`: every project must parse without credentials | `dbt/**/*.{sql,yml,yaml,csv,py}` |
| `sqlfluff lint` | `cd dbt/dbt_example && sqlfluff lint models` | `dbt/dbt_example/models/**/*.sql` |
| `dagster definitions validate` | Every code location must load | `src/**` and `dlt_pipelines/**` (`*.py`, `*.yaml`) |
| `terraform fmt` | `terraform fmt -recursive terraform` | `*.tf` |
| `validate-configs` | `terraform/config/_validation/validate_configs.py`: every YAML matches its JSON schema, references resolve, required layers, environments, computes and roles are present | `terraform/config/**/*.{yaml,json}` |

Details agents trip over:

- **The sqlfluff hook is hard-wired to `dbt/dbt_example`.** A second dbt project needs its own hook entry; the `.sqlfluff` config in `dbt/` is shared. See [adding a project](../development/adding-projects.md).
- **`dbt parse` needs packages.** The hook and the Dagster validation both parse the dbt projects; without `just dbt-all deps` they fail before your change is even looked at.
- **`just pre-commit` runs with `.env` loaded** (`just` loads it into every recipe), so the Dagster hook parses dbt with whatever `DBT_TARGET` says, and `ENVIRONMENT` when that is unset. CI has no `.env` and sets `DBT_TARGET=dummy` explicitly.
- **`terraform fmt` calls the `terraform` binary.** It only fires on `*.tf` changes, which are administrator territory; an engineer's machine does not need Terraform installed. The YAML hook (`validate-configs`) runs through `uv` and works everywhere.

### 2. CI

`.github/workflows/ci.yml` repeats everything in four independent jobs:

| Job | Steps |
|---|---|
| `python` | `uv sync`, `ruff format --check .`, `ruff check .`, `ty check`, `pytest` |
| `dbt-and-dagster` | `dbt_all.py deps`, `dbt_all.py parse --target dummy`, `sqlfluff lint models` in `dbt/dbt_example`, `dagster definitions validate -w workspace.yaml` (with `DBT_TARGET=dummy`) |
| `terraform` | `terraform fmt -check -recursive terraform`, `init -backend=false`, `validate`, then `validate_configs.py` through `uv` |
| `docs` | `mkdocs build --strict` (a broken link fails the build) |

`just check` is the local equivalent of the first two jobs plus the YAML validation of the third. Run `just docs build --strict` after editing `docs/`.

!!! danger "Never bypass hooks"
    `--no-verify` is forbidden. Agents never run `git commit` at all (humans own git, see [Git workflow](../conventions/git-workflow.md)), but the rule extends to advice: when a hook fails, fix the cause; never suggest bypassing it. CI runs the same checks and fails the pull request anyway.

## Where each rule lives

Look up rules on their canonical page; each page names the config file that enforces it.

| Concern | Canonical page | Config (ground truth) |
|---|---|---|
| Python formatting, lint rules, typing | [Python style](../conventions/python-style.md) | `pyproject.toml`: `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ty.src]` |
| SQL formatting and syntax | [SQL style](../conventions/sql-style.md) | `dbt/.sqlfluff` and `dbt/.sqlfluffignore` |
| dbt layers, reference rule, model and test placement | [dbt style guide](../conventions/dbt-style-guide.md) | `dbt/*/dbt_project.yml` |
| Names of models, columns, sources, seeds, assets, Snowflake objects | [Naming](../conventions/naming.md) | Convention for code; `terraform/main.tf` and `dbt_common.generate_schema_name` generate the Snowflake names |
| Snowflake objects per project and environment | [Snowflake provisioning](../administration/snowflake-provisioning.md) | `terraform/config/**/*.yaml`, checked by `terraform/config/_validation/schemas/*.json` |
| pytest layout, dbt tests, definition validation | [Testing](../development/testing.md) | `tests/`, `dbt/dbt_example/tests/`, `dbt/dbt_common/tests/generic/` |
| Hook list and order | This page | `.pre-commit-config.yaml` |
| CI jobs | This page | `.github/workflows/ci.yml` |
| Git and pull requests | [Git workflow](../conventions/git-workflow.md) | GitHub settings |

The [Conventions overview](../conventions/index.md) has the same map from the human angle.

## dbt YAML

No formatter rewrites dbt YAML in this repo; `check-yaml` only validates it. Keep to the shape of the existing files: one YAML per model in a sibling `_conf/` folder (never next to the SQL), `version: 2`, a `description` per model and per column, `data_type` per column, and named tests under `data_tests`. Where the YAML goes and what it must contain: [Adding a dbt model](../development/adding-dbt-models.md).

## Terraform YAML

The same applies to `terraform/config/`: one YAML per organisation, team, project, environment, layer, role, compute and user. Every file starts with a `# yaml-language-server: $schema=...` line pointing at its JSON schema, so an editor validates as you type; `just tf-validate-config` validates everything, including cross-references (a project naming a layer that does not exist is an error, a disabled one a warning) and the required items every project must list. Agents may edit these files for an administrator; applying them (`just tf plan`, `just tf apply`) is a human decision.

## Troubleshooting

Quick fixes for check failures. Setup and runtime failure modes with more background: [Troubleshooting](../getting-started/troubleshooting.md).

| Error | Cause | Fix |
|---|---|---|
| `dbt parse` fails with a missing package or macro | `dbt deps` has not run in that project | `just dbt-all deps` |
| `dagster definitions validate` fails on the `dbt_example` location | The location parses the dbt project on load and that parse failed | `just dbt parse` shows the real error |
| `sqlfluff: dbt templater error` | dbt packages missing in the project | `just dbt deps` (or `just dbt-all deps`) |
| `ruff check: unfixable` | A lint error ruff cannot auto-fix | Fix it by hand, re-run `just lint` |
| `ty check: error[...]` | Wrong annotation or wrong code | Fix the type or the code |
| `check-added-large-files` fails | A file exceeds the hook's size limit | Do not commit data files; local data lives in `.dlt/data/` and Snowflake |
| `detect-private-key` fails | A `.p8` or PEM key ended up in the tree | Keys live under `~/.snowflake/keys/`; the path goes in `.env`, never the key |
| `terraform fmt` fails with "command not found" | A `.tf` change on a machine without Terraform | Administrators install Terraform; engineers leave `terraform/*.tf` alone |
| `validate-configs` reports `[projects/...]` or `[roles/...]` errors | A YAML under `terraform/config` breaks its schema, names a missing key, or lacks a required item | `just tf-validate-config` prints the file, the field and the message; fix the YAML |
| Port 3000 already in use | A previous Dagster instance is still running | `just stop`, then `just start` |
| `JWT token is invalid` on any Snowflake step | The key in `.env` does not match the key registered on the user | `just snowflake setup` again, let it re-register the existing key |

## Related pages

- [AI agents overview](index.md): how the repo talks to agents, the rules, the validation loop
- [Development](../development/index.md): the daily loop
- [Testing](../development/testing.md): pytest, dbt tests and definition validation in depth
- [Conventions](../conventions/index.md): all style pages and the rules-to-config map
- [Git workflow](../conventions/git-workflow.md): humans-only git
- [Command reference](../reference/commands.md): every `just` recipe
- [Troubleshooting](../getting-started/troubleshooting.md): setup and runtime failure modes
