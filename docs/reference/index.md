---
icon: material/book-open-variant
---

# Reference

The rest of the site explains how the platform works. This section is for looking things up:
the rules, the names, the recipes, the variables, and what a word means when you have forgotten.

## The hard musts

`AGENTS.md` is the instruction file every AI agent reads, and it is just as binding for people.
Its non-negotiables:

1. **Never hardcode credentials.** The `SNOWFLAKE_*` block in `.env`, written by `just sf setup`,
   is the only place they live. See [Environment variables](environment-variables.md).
2. **Never bypass pre-commit.** No `--no-verify`. Fix the cause; CI runs the same checks and fails
   the pull request anyway. See [What runs when](git-workflow.md#what-runs-when).
3. **Reference only the layer directly below.** STG cannot `ref()` an INT model, MRT cannot
   `ref()` an EXP model. See [Layer reference rules](dbt-style-guide.md#layer-reference-rules).
4. **Validate before presenting work.** `just fmt`, `just validate`, `just test`, `just check`.
   See [the validation loop](ai-agents.md#the-validation-loop).
5. **Use existing patterns** before adding an abstraction. `dlt_pipelines/`,
   `src/orchestrator/` and the models under `dbt/` already have a shape for nearly everything.

Per surface, one line each:

| Surface | The rule | Page |
|---|---|---|
| Python | ruff (line length 120, rules `E F I UP B`), ty, full annotations, `X \| None` never `Optional[X]` | [Python style](python-style.md) |
| SQL | sqlfluff Snowflake dialect: keywords upper, identifiers lower, leading commas, 2-space indent, `CAST()` not `::`, CTEs not subqueries | [SQL style](sql-style.md) |
| dbt | A `_conf/<model>.yml` per model, a named test on every key, the layer rules | [dbt style guide](dbt-style-guide.md) |
| Names | `stg__<source>__<entity>`, `int__<domain>__<entity>`, `(dim\|fct\|brg\|agg)__<domain>__<entity>`, `exp__<domain>__<entity>` | [Naming](naming.md) |
| Commits | Conventional commits; release-please derives the version, so never bump it by hand | [Commit messages](git-workflow.md#commit-messages) |

## The pages

| Page | What it holds |
|---|---|
| [Python style](python-style.md) | ruff and ty, type annotations, naming, error handling, the patterns to reuse instead of reinventing |
| [SQL style](sql-style.md) | The sqlfluff rule set in practice: capitalisation, commas, casts, joins, CTEs, Jinja |
| [dbt style guide](dbt-style-guide.md) | Layers and reference rules, what every model needs, `_conf/` YAML, sources, seeds, tests, macros, `dbt_common` |
| [Naming](naming.md) | Every name in one place: models, columns, tests, dlt tables, asset keys, Dagster definitions, Snowflake objects, Terraform config files |
| [Git workflow](git-workflow.md) | Branches, conventional commits, releases, the protected `main`, code owners, and what runs when |
| [Commands](commands.md) | Every `just` recipe, for engineers and administrators |
| [Environment variables](environment-variables.md) | Everything `.env` can hold, what the tooling sets itself, and how the values turn into schema names |
| [Glossary](glossary.md) | The concept and tool terms these docs use, one anchor per term |
| [For AI agents](ai-agents.md) | The agent entry points, the validation loop, what to run after changing what, and the pitfalls |

## Where the rules live

Each rule has one config file that decides it and at least one check that enforces it.

| Concern | Config | Enforced by |
|---|---|---|
| Python lint + format | `pyproject.toml`, `[tool.ruff]` | pre-commit (`ruff format`, `ruff check --fix`), CI `python` job |
| Python types | `pyproject.toml`, `[tool.ty]` | pre-commit (`ty check`), CI `python` job |
| Python tests | `pyproject.toml`, `[tool.pytest.ini_options]` | CI `python` job (not a pre-commit hook: run `just test` yourself) |
| SQL lint | `dbt/.sqlfluff` (shared by every project) | pre-commit (`sqlfluff lint models`, one hook per project), CI `dbt-and-dagster` job |
| dbt validity | `dbt/*/dbt_project.yml`, `dbt/profiles.yml` | pre-commit (`dbt parse` with the `local` target, on both parsers), CI `dbt-and-dagster` job |
| Dagster definitions | `workspace.yaml` | pre-commit (`dagster definitions validate` plus the asset-key check), CI `dbt-and-dagster` job |
| Terraform formatting | `terraform/` | pre-commit (`terraform fmt`), CI `terraform` job |
| Terraform YAML | `terraform/config/_validation/schemas/*.json` | pre-commit (`validate-configs`), CI `terraform` job, `just tf-validate-config` |
| Docs | `mkdocs.yml` | pre-commit (`check_doc_fences.py`), CI `docs` job (the fence check and `zensical build --strict`) |

`just check` runs all of it except the Terraform CLI part; `just pre-commit` runs every hook on
every file. The full list of recipes is on [Commands](commands.md), the hook and job tables on
[Git workflow](git-workflow.md#what-runs-when).
