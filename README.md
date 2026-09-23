# Data Mesh Platform Starter

A runnable starter for a **data mesh platform on Snowflake**: **Dagster** orchestrates, **dlt**
ingests, **dbt** transforms, **Terraform** provisions. It implements the conceptual model of
[rootcube/platform](https://github.com/rootcube/platform) (Organisation, Team, Project,
Environment, Layer, Role, Compute) in one small repository that runs on a laptop and grows into a
multi-project mesh: one dbt project and one Dagster code location per project, a shared
`dbt_common` package, and YAML-driven Snowflake provisioning.

> Full documentation lives in `docs/` and is served with `just docs` (MkDocs Material). This
> README is the quickstart and a map.

## Quickstart (engineer)

Prerequisites: [`just`](https://github.com/casey/just) and git. Everything else is installed for you.

```bash
git clone git@github.com:rootcube/enexis-dev-day.git && cd enexis-dev-day
just init              # uv, .venv (Python 3.13), .env, dbt packages
just snowflake setup   # one-time login, key pair registered on your user, .env filled in
just snowflake check   # proves key-pair login works (`just snowflake context` re-points .env at a project later)
just start             # Dagster UI on http://localhost:3000
```

Run bare `just` for the full recipe list, or see the docs page *Reference > Commands*.

## What is inside

```
src/orchestrator/            Dagster package
├── locations/dlt/           code location: every dlt ingest pipeline
├── locations/dbt/           shared factory + one code location per dbt project (dbt_example/)
├── resources/snowflake.py   the one place that reads SNOWFLAKE_* and ENVIRONMENT
└── utils/
dlt_pipelines/               dlt package: pipelines/ingest/<source>/ (knmi to start with)
dbt/                         profiles.yml (shared) + dbt_common (package) + dbt_example (project)
terraform/                   Snowflake provisioning from terraform/config (administrators)
scripts/                     snowflake.py (key-pair setup), info.py, dbt_all.py
docs/ + mkdocs.yml           the documentation site
```

Data flows KNMI API -> dlt -> `_SRC` -> dbt (`_STG`, `_INT`, `_MRT`, `_EXP`) inside the project
database `DB_EXAMPLE_<ENV>`, with Dagster orchestrating both. In development every engineer
works in personal schemas (`DBT_<NAME>_STG`) of the shared `DB_EXAMPLE_DEV`.

## For platform administrators

`terraform/README.md` (also in the docs under *Administration*) walks through the one-time
Snowflake bootstrap, the YAML configuration under `terraform/config`, and onboarding people.

## Working with AI agents

`AGENTS.md` is the canonical instruction set (`CLAUDE.md` is a symlink to it); the docs section
*AI agents* carries the per-technology guides and standards.

## License

GPL-3.0, see `LICENSE`.
