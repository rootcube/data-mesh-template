---
icon: material/robot-outline
---

# For AI agents

This repository is written to be worked on by AI coding agents. `AGENTS.md` in the root is the
canonical instruction file; this page is the map around it: the entry points, the loop to run,
what to run after touching what, and the things that go wrong here. It is also the fastest route
in for a human in a hurry.

## Entry points

| File | Read by | What it is |
|---|---|---|
| `AGENTS.md` | every agent | Behavior rules, the project overview and platform model, the directory map, the commands, the conventions, the pitfalls. Read it completely before changing anything |
| `CLAUDE.md` | Claude Code | One line, `@AGENTS.md`, read as an import |
| `docs/` | every agent | These pages, which hold the rules `AGENTS.md` summarizes. It links them by path, so a clone is enough; `just docs` renders them for humans |

No MCP server is configured here, for Snowflake or for anything else. Agents look at Dagster,
dbt, dlt and Snowflake through the `just` recipes (`just sf check`, `just sf query "..."`,
`just dagster ...`) and by reading files.

!!! tip "Rules live in one file"
    Project rules go in `AGENTS.md` only. `CLAUDE.md` stays that single line, an import rather
    than a symlink: a Windows checkout with `core.symlinks=false` turns a symlink into a 9-byte
    text file, which instructs nobody.

## How to work here

| Rule | In practice |
|---|---|
| Read before writing | Assets, resources, models, tests and pipelines all have a shape here already. Find it and follow it |
| Minimal changes | What was asked, nothing more: no drive-by refactors, no unsolicited docstrings, one thing per change |
| Verify before claiming | Check that the file, function or recipe you name actually exists |
| Type hint everything | Every parameter and every return type, in Python 3.13 syntax. See [Type annotations](python-style.md#type-annotations) |
| Never commit or push | No `git commit`, no `git push`, no branches. Read-only git is fine; a human reviews the working tree and commits it. See [Git workflow](git-workflow.md) |
| Never bypass pre-commit, never hardcode credentials | Together with the rest of [the hard musts](index.md#the-hard-musts) |
| Challenge, don't comply | Push back on an approach that breaks a rule or an existing pattern, ask before building something that looks wrong, name the risk |

## The validation loop

Run it and make it pass before presenting work. Everything in it also runs in pre-commit and CI,
so skipping a step only postpones the failure.

--8<-- "docs/includes/validation-loop.md"

## What to run after changing what

| Changed | Also run |
|---|---|
| Python under `src/`, `dlt_pipelines/`, `scripts/`, `tests/` | `just typecheck`, `just test`, `just validate` |
| A dlt pipeline, its `defs.yaml` or a dbt source YAML | `just validate` (it checks that the dlt and dbt asset keys still match), then `just dlt run <source>` |
| dbt models, seeds or macros | `just dbt-all deps` when packages changed, `just dbt parse`, `just dbt build --select <model>+` |
| Dagster definitions or `workspace.yaml` | `just validate` |
| `terraform/config/*.yaml` | `just tf-validate-config`, and read [On the administrator side](#on-the-administrator-side) before going further |
| `docs/` or `mkdocs.yml` | `just docs build --strict`, and the fence check that `just check` runs |
| Dependencies in `pyproject.toml` | `uv lock`, and leave `uv.lock` in the change: CI installs with `uv sync --locked` |

`just dbt build`, `just dlt run` and every `just sf` recipe reach Snowflake and need a filled
`.env` that only a human can create ([Snowflake authentication](../start/snowflake-auth.md)).
Without one, uncomment `DBT_TARGET=dummy` in `.env` so dbt parses against the in-memory DuckDB,
exactly as CI does.

## On the administrator side

Editing `terraform/config/*.yaml` is fair game and cheap to check: `just tf-validate-config`
validates every file against its JSON schema and resolves the cross-references. A new project is
a copy of `projects/example.yaml` with its own `code`; a new person is a file under `users/`
listing project roles per environment, and their personal schemas exist only once somebody
applies it.

Everything past that is a human administrator's call against a real account: `just tf plan`,
`just tf apply`, `just tf clean`, `init.sql`, `account_settings.sql`, and registering a key on
another user. Describe the change and stop. See
[Snowflake provisioning](../operate/snowflake-provisioning.md).

## Pitfalls

The mistakes that actually happen here. Check failures with a mundane cause are in
[Troubleshooting](../start/troubleshooting.md).

| Pitfall | What to do |
|---|---|
| The dbt code locations read `target/manifest.json`, and only `dagster dev` re-parses on load | `just dbt-all deps`, then `just dbt-all parse --target dummy`; `just init` and `just check` do both |
| A model that references two layers down, or up | Only the layer directly below, see [Layer reference rules](dbt-style-guide.md#layer-reference-rules) |
| A model without its `_conf/<model>.yml`, or with the YAML next to the SQL | [What every model needs](dbt-style-guide.md#every-model-needs) |
| A second project building the `dbt_common` models, writing the same tables twice | Exactly one project builds them, see [dbt_common](dbt-style-guide.md#dbt_common) |
| A model without a `+schema`, which lands in an unprovisioned schema | [How the values become schema names](environment-variables.md#how-the-values-become-schema-names) |
| Schedules and sensors are stopped in `dev` and `dummy` and running elsewhere | Leave the default alone; switch one on in the UI to test it |
| A one-off job, schedule or sensor written by hand in a `definitions.py` | They are derived per source and per project; extend the factory, see [Orchestration](../understand/orchestration.md) |
| A `.env` value with special characters | Single quotes, see [Quoting](environment-variables.md) |

## The canonical page per technology

Read the one that matches the code you are changing; none of them restate another.

| Working on | Read |
|---|---|
| dlt pipelines | [Ingestion](../understand/ingestion.md), [Adding a dlt load](../build/adding-dlt-loads.md) |
| dbt models | [Transformation](../understand/transformation.md), [dbt style guide](dbt-style-guide.md), [SQL style](sql-style.md), [Adding a dbt model](../build/adding-dbt-models.md) |
| Dagster | [Orchestration](../understand/orchestration.md), [Adding Python assets](../build/adding-python-assets.md) |
| Snowflake objects, roles, authentication | [Snowflake](../understand/snowflake.md), [Snowflake provisioning](../operate/snowflake-provisioning.md) |
| Python | [Python style](python-style.md), [Testing](../build/testing.md) |
| Naming anything | [Naming](naming.md) |
| Running anything | [Commands](commands.md) |

## Prompting an agent

- **Name the page** for what you are touching: *"follow `docs/reference/dbt-style-guide.md` and
  add an INT model for ..."*. That pulls the rules into context immediately.
- **Point at an example.** *"Do it like the `knmi` pipeline"* beats describing a pattern.
- **One task per prompt.** The rules forbid bundled changes; a three-part prompt asks for one
  anyway.
- **Say which environment** if it is not `dev`. An agent cannot see `tst`, `acc` or `prd` from a
  laptop.
- **Expect pushback.** An agent telling you the plan breaks the layer rules is the system working.
