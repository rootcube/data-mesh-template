# AGENTS.md

Instructions for AI agents working in this repository. Read this file completely before making changes.

## Agent behavior

### Communication style
- **Be brief.** Lead with the answer or action. Skip preamble, filler, and restating what was asked.
- **Be precise.** Use exact file paths, line numbers, function names. No hand-waving.
- **Be direct.** Say what is wrong, what needs to change, and why. Do not soften bad news.

### Challenge, don't comply
- **Push back** when an approach is suboptimal, fragile, or violates project conventions. Say so clearly.
- **Ask why** before implementing something that seems wrong. "Are you sure?" is a valid response.
- **Suggest alternatives** when there is a better path. Do not just do what is asked if it creates debt.
- **Flag risks** proactively: performance, security, maintainability, breaking changes.
- **Never agree just to be agreeable.** Honest feedback prevents costly mistakes later.

### Working style
- **Read before writing.** Understand existing code, patterns, and conventions before proposing changes.
- **Verify before claiming.** Check that files, functions, and paths actually exist. Do not invent code.
- **Minimal changes.** Do what is asked, nothing more. No drive-by refactors, no unsolicited docstrings, no "while I'm here" improvements.
- **Follow existing patterns.** Assets, resources, models and tests all have established shapes here. Use them.
- **Run the checks.** `just fmt`, `just typecheck`, `just test`, `just validate` before presenting work. The skill pages under `docs/ai-agents/` list technology-specific validation.
- **One thing at a time.** Do not bundle unrelated changes. Keep diffs small and reviewable.
- **Never commit or push.** Do not run `git commit`, `git push`, or create branches. Humans do all git writes. Read-only git commands (`git status`, `git diff`, `git log`) are fine.
- **Type hint everything.** Every function signature gets full annotations, parameters and return type.

### Keep it simple
- **No over-engineering.** Solve the problem at hand, not hypothetical future problems.
- **Flat is better than nested.** More than three levels of indentation means refactor.
- **Small functions.** One thing per function; if you cannot describe it in one sentence, split it.
- **Readable over clever.** Write code a junior developer can follow.
- **No unnecessary indirection.** No wrapper that only calls another function; no class where a function will do.
- **Three is not a pattern.** Extract a helper only when the same logic appears in genuinely different contexts.
- **Limit function arguments.** More than four parameters is a smell; use a dataclass.
- **Delete dead code.** Do not comment it out; git history keeps it.

## Project overview

A runnable starter for a data mesh platform on Snowflake: **Dagster** orchestrates, **dlt**
ingests, **dbt** transforms, **Terraform** provisions. It implements the conceptual model of
rootcube/platform: an **Organisation** has **Teams**, a Team owns **Projects**, a Project exists
in **Environments** (dev, tst, acc, prd), and each Project × Environment has **Layers** (schemas),
**Roles** (grants) and **Computes** (warehouses). One dbt project and one Dagster code location
per Project; `dbt_common` is shared. The starter ships one project, `example`.

## Skill references

Per-technology guides live in the docs site under `docs/ai-agents/` (single source of truth; they
link to the convention pages under `docs/conventions/` instead of restating them):

- [Dagster](docs/ai-agents/dagster.md): code locations, components, assets, jobs, resources
- [dbt](docs/ai-agents/dbt.md): projects, layers, models, macros, `dbt_common`
- [dlt](docs/ai-agents/dlt.md): sources, pipelines, the Snowflake destination, the Dagster component
- [Snowflake](docs/ai-agents/snowflake.md): the platform model in Snowflake, key-pair auth, naming, Terraform
- [Python](docs/ai-agents/python.md): style, type hints, tests, dependencies
- [SQL](docs/ai-agents/sql.md): formatting, sqlfluff rules, Jinja patterns
- [Standards](docs/ai-agents/standards.md): pre-commit, CI, the validation loop

## Architecture

```
Sources (KNMI API, ...) -> dlt -> _SRC -> dbt (_STG -> _INT -> _MRT -> _EXP) -> consumers
                                    Dagster orchestrates both, all inside DB_<PROJECT>_<ENV>
```

Snowflake naming: database `DB_<PROJECT>_<ENV>`, layer schemas `_SRC`, `_REF`, `_STG`, `_INT`,
`_MRT`, `_EXP`, `_MTD` (run metadata), `_TMP` (test failures), roles `RL_<PROJECT>_<ENV>__<PURPOSE>`
(`ENG`, `ANL`, `ING`, `TFM`), warehouses `WH_<PROJECT>_<ENV>[__<COMPUTE>_<SIZE>]`. In `dev` every
engineer works in personal schemas prefixed with `SNOWFLAKE_SCHEMA` (`DBT_INFO_STG`); the other
environments use the provisioned `_<LAYER>` schemas. `SnowflakeSettings.schema_for_layer()` and
`dbt_common.generate_schema_name` implement that rule; dbt source YAML repeats it with `env_var`.
Detail: [Architecture](docs/architecture/index.md), [Concepts](docs/concepts/index.md).

## Directory structure

`workspace.yaml` is the authoritative list of Dagster code locations.

```
src/orchestrator/                 # Dagster package
├── locations/dlt/definitions.py  #   loads the dlt_pipelines component tree (one asset per dlt resource)
├── locations/dbt/shared.py       #   build_dbt_defs(): one code location per dbt project
├── locations/dbt/dbt_example/    #   definitions.py + defs/dbt/defs.yaml (DbtProjectComponent)
├── resources/snowflake.py        #   SnowflakeSettings.from_env(): the only reader of SNOWFLAKE_* and ENVIRONMENT
└── utils/dotenv.py               #   .env editing used by scripts/snowflake.py
dlt_pipelines/                    # dlt package: pipelines/ingest/<source>/{constants,source,pipelines}.py + defs.yaml
dbt/                              # profiles.yml (shared profile `default`: dev/tst/acc/prd = Snowflake key pair, dummy = in-memory DuckDB)
├── .sqlfluff                     #   shared lint config (run sqlfluff from inside a project)
├── dbt_common/                   #   package: macros (schema naming, query tag, run logging, metadata upload), generic dims/seeds, generic tests
└── dbt_example/                  #   project: models/02_stg 03_int 04_mrt 05_exp, sources/, seeds/, packages.yml (local dbt_common)
terraform/                        # administrators: YAML config (organisations, teams, projects, environments, layers, roles, computes, users) -> Snowflake
scripts/                          # snowflake.py (key-pair setup/check/query/keygen), info.py, dbt_all.py
tests/                            # pytest, offline only
docs/ + mkdocs.yml                # the documentation site
```

Locations load in their own subprocess and never import each other; cross-location lineage
resolves through shared asset keys (dbt sources declare `config.meta.dagster.asset_key` matching
the dlt asset key `dlt/ingest/<source>/<entity>`). dagster-dbt keys are `<layer>/<name>` (the `+schema` config plus the model name, e.g. `stg/stg__knmi__climate_hourly`).

## Common commands

```bash
just init             # uv + .venv + .env + dbt deps
just snowflake setup  # one-time key-pair setup (interactive login)
just snowflake context # (re)point .env at a project from the roles granted to you, no login
just start            # Dagster UI on :3000
just validate         # dagster definitions validate -w workspace.yaml
just dbt build        # dbt in dbt/dbt_example (just project=dbt_x dbt ... for another project)
just dlt run knmi     # one dlt pipeline outside Dagster
just fmt / lint / typecheck / test / check
just tf plan          # Terraform (administrators); just tf-validate-config checks the YAML
just docs             # docs site on :8000 (`just docs build --strict` after editing docs/)
```

When a change alters behavior documented under `docs/` (commands, env vars, conventions,
architecture), update the affected page in the same change set and verify with
`just docs build --strict`.

## Code conventions

Full rules: [Conventions](docs/conventions/index.md). The hard musts:

- **Python:** ruff (line length 120, rules E F I UP B), ty for types. Type-hint everything, `X | None` not `Optional[X]`. See [Python style](docs/conventions/python-style.md).
- **SQL (dbt):** sqlfluff (Snowflake dialect), leading commas, 2-space indent, uppercase keywords, lowercase identifiers, `CAST()` not `::`, `LEFT JOIN` never `RIGHT JOIN`, CTEs (`cte_` prefix) over subqueries. See [SQL style](docs/conventions/sql-style.md) and the [dbt style guide](docs/conventions/dbt-style-guide.md).
- **Naming:** `stg__<source>__<entity>`, `int__<domain>__<entity>`, `(dim|fct|brg|agg)__<domain>__<entity>`, `exp__<domain>__<entity>`; seeds `seed_<name>`; sources `src_<source>.yml`; dlt tables `<source>__<entity>` in `_SRC`. See [Naming](docs/conventions/naming.md).
- **Secrets:** never in files. `SNOWFLAKE_*` come from `.env`, written by `just snowflake setup`.

## Adding things

- **dlt load** ([guide](docs/development/adding-dlt-loads.md)): a folder `dlt_pipelines/pipelines/ingest/<source>/` with `pipelines.py` (module-level `source` and `pipeline`, `table_name=<source>__<entity>`), `source.py`, `constants.py` and a `defs.yaml`; then a `src_<source>.yml` in the dbt project and a staging model.
- **dbt model** ([guide](docs/development/adding-dbt-models.md)): `models/<layer>/<domain>/<name>.sql` plus its YAML in a sibling `_conf/` folder. Models reference only the layer directly below.
- **project** ([guide](docs/development/adding-projects.md)): a `terraform/config/projects/<project>.yaml`, a copy of `dbt/dbt_example` and of `src/orchestrator/locations/dbt/dbt_example`, one line in `workspace.yaml`. Exactly one project builds the `dbt_common` models.
- **Python asset** ([guide](docs/development/adding-python-assets.md)): in the location that owns it; a genuinely separate concern is a new code location in `workspace.yaml`.

## Critical rules

1. **Never hardcode credentials.** Environment variables only.
2. **Never bypass pre-commit.** Fix the issue instead.
3. **Follow the dbt style guide** and the layer rules.
4. **Test your changes.** `just test` for Python, `dbt test` (via `just dbt build`) for SQL, `just validate` for Dagster, `just tf-validate-config` for Terraform YAML.
5. **Use existing patterns** before creating new abstractions.

## Common pitfalls

- **`dbt deps` first.** The Dagster dbt location parses the project on load; without packages it fails. `just dbt-all deps`.
- **Every dbt model needs its `_conf/<model>.yml`** with column descriptions, `data_type` and named tests.
- **Do not reference across layers.** STG cannot ref INT, MRT cannot ref EXP.
- **Asset key collisions.** Two dbt projects building the same `dbt_common` models produce duplicate asset keys across code locations. Only one project builds them; others disable `dbt_common` models.
- **Source YAML cannot call macros.** The source layer schema is spelled out with `env_var` in `sources/*.yml`; keep it in step with `dbt_common.generate_schema_name`.
- **No quotes in `.env`.** `just` and Docker pass quoted values literally.
