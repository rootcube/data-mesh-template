---
icon: material/ruler-square
---

# Conventions

This repository is small, but it has the same surfaces as a production data platform: Dagster
code locations, a shared dbt package plus one dbt project per mesh node, a dlt package, Terraform
configuration, and three languages (Python, SQL, YAML). Humans and AI agents both write here.
These conventions keep all of it looking like one person wrote it, and they hold as the mesh
grows from one project to many.

## Why this matters here

- **One repo, many surfaces.** A single change can touch a dlt pipeline, its `defs.yaml`, a dbt
  source, a staging model and its `_conf/` YAML. Consistent patterns mean you can read any of them
  without re-learning the codebase.
- **Many projects, one shape.** Every project is a copy of `dbt_example` with its own name, so a
  convention that holds in one holds in all of them. Naming is what keeps `DB_<PROJECT>_<ENV>`,
  `dbt_<project>` and `job_dbt_<project>_build_all` lined up.
- **AI agents write code here.** Agents follow the same rules you do. `AGENTS.md` and the
  [AI agent pages](../ai-agents/index.md) point at this section instead of restating it, so human
  and agent output look the same in review.
- **Most of it is enforced.** Pre-commit hooks and the CI workflow run ruff, ty, pytest,
  `dbt parse`, sqlfluff, `dagster definitions validate`, `terraform fmt`, the Terraform YAML
  validation and a strict docs build. If it is not formatted right, it does not merge. See
  [Git workflow](git-workflow.md).

## Critical rules

From `AGENTS.md`, and non-negotiable:

1. **Never hardcode credentials.** Environment variables only: the `SNOWFLAKE_*` block in `.env`,
   written by `just sf setup`.
2. **Never bypass pre-commit.** Fix the issue instead of reaching for `--no-verify`.
3. **Follow the [dbt style guide](dbt-style-guide.md)** and the layer rules: models reference only
   the layer directly below.
4. **Test your changes.** `just test` for Python, `dbt test` (part of `just dbt build`) for SQL,
   `just validate` for Dagster, `just tf-validate-config` for the Terraform YAML.
5. **Use existing patterns** before creating new abstractions. Check `dlt_pipelines/`,
   `src/orchestrator/` and the existing dbt models first.

## Keep it simple

The design philosophy, straight from `AGENTS.md`:

- **Solve the problem at hand**, not hypothetical future problems. No abstractions, factories or
  patterns "just in case".
- **Small, flat functions.** One thing per function. More than three levels of indentation means
  refactor; more than four parameters means use a dataclass.
- **Readable over clever.** Write code a junior developer can follow.
- **No unnecessary indirection.** No wrapper that only calls another function; no class where a
  function will do.
- **Three is not a pattern.** Extract a helper only when the same logic appears in genuinely
  different contexts.
- **Delete dead code.** Do not comment it out; git history keeps it.

## In this section

<div class="grid cards" markdown>

-   :material-language-python:{ .lg .middle } **[Python style](python-style.md)**

    ---

    ruff (line length 120, rules `E F I UP B`), ty, full type annotations in Python 3.13 syntax,
    naming, and the patterns to reuse.

-   :material-code-tags:{ .lg .middle } **[SQL style](sql-style.md)**

    ---

    The sqlfluff Snowflake rule set in practice: uppercase keywords, leading commas, 2-space
    indent, `CAST()` not `::`, good-vs-bad examples, how to run the linter.

-   :material-book-cog:{ .lg .middle } **[dbt style guide](dbt-style-guide.md)**

    ---

    Layers and reference rules, `_conf/` YAML placement, tests, materializations, sources, seeds,
    macros and the shared `dbt_common` package.

-   :material-tag-text:{ .lg .middle } **[Naming](naming.md)**

    ---

    One naming reference: dbt models per layer, columns, dlt tables and asset keys, Dagster
    locations and jobs, Snowflake databases, schemas, roles and warehouses.

-   :material-git:{ .lg .middle } **[Git workflow](git-workflow.md)**

    ---

    Short-lived branches, pull requests, conventional-commit style messages, the pre-commit hooks
    and the CI jobs.

</div>

## Where the rules live

| Concern | Config | Enforced by |
|---|---|---|
| Python lint + format | `pyproject.toml`, `[tool.ruff]` | pre-commit (`ruff format`, `ruff check --fix`), CI `python` job |
| Python types | `pyproject.toml`, `[tool.ty]` | pre-commit (`ty check`), CI `python` job |
| Python tests | `pyproject.toml`, `[tool.pytest.ini_options]` | CI `python` job (not a pre-commit hook: run `just test` yourself) |
| SQL lint | `dbt/.sqlfluff` (shared by every project) | pre-commit (`sqlfluff lint models`), CI `dbt-and-dagster` job |
| dbt validity | `dbt/*/dbt_project.yml`, `dbt/profiles.yml` | pre-commit (`dbt parse` with the `dummy` target), CI `dbt-and-dagster` job |
| Dagster definitions | `workspace.yaml` | pre-commit (`dagster definitions validate`), CI `dbt-and-dagster` job |
| Terraform formatting | `terraform/` | pre-commit (`terraform fmt`), CI `terraform` job |
| Terraform YAML | `terraform/config/_validation/schemas/*.json` | pre-commit (`validate-configs`), CI `terraform` job, `just check` |
| Docs | `mkdocs.yml` | CI `docs` job (`zensical build --strict`) |

`just check` runs the Python, dbt, Dagster and Terraform YAML part of that list locally (lint,
typecheck, test, dbt parse, Dagster validate, config validation); `just pre-commit` runs every
hook on every file. Full list: [Commands](../reference/commands.md).
