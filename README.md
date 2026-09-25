# Data Mesh Platform Starter

A runnable starter for a **data mesh platform on Snowflake**: **Dagster** orchestrates, **dlt**
ingests, **dbt** transforms, **Terraform** provisions. It implements the conceptual model of
[rootcube/platform](https://github.com/rootcube/platform) (Organisation, Team, Project,
Environment, Layer, Role, Compute) in one small repository that runs on a laptop and grows into a
multi-project mesh: one dbt project and one Dagster code location per project, a shared
`dbt_common` package, and YAML-driven Snowflake provisioning.

> Full documentation lives in `docs/` and is served with `just docs` (Zensical). This
> README is the quickstart and a map.

## Quickstart (engineer)

### Install

Two tools by hand, [`just`](https://github.com/casey/just) and git; `just init` installs the rest
(uv, Python 3.13, the virtual environment, the dbt packages).

```bash
# macOS / Linux (Homebrew)
brew install just git

# Windows (winget, PowerShell)
winget install --id Casey.Just -e
winget install --id Git.Git -e
```

Inside the checkout, `just install <tool>` adds the optional extras: `terraform` (needed for the
fresh-account path), `direnv`, `gh`, or `all`. Details and alternatives:
[Prerequisites](docs/getting-started/prerequisites.md).

### Run

```bash
git clone git@github.com:rootcube/data-mesh-template.git && cd data-mesh-template
just setup       # init, then a one-question wizard (see below), then your .env
just start       # Dagster UI on http://localhost:3000
```

`just setup` runs `just init` and then asks which kind of account this is:

1. **Fresh**, you hold `ACCOUNTADMIN` and nothing is provisioned yet (a free
   [trial](https://signup.snowflake.com/) is enough): it installs Terraform if missing, creates the
   Terraform service user, provisions the `example` project, registers your key pair and writes
   `.env`. It asks for the organization, account name, user and password. Step by step:
   [Snowflake Trial Account setup](docs/administration/snowflake-trial-account-setup.md).
2. **Provisioned**, an administrator ran Terraform and granted you a project role: one interactive
   login, your key pair registered on your user, `.env` filled in. Same as `just sf setup`.

`just sf check` proves the key-pair login works; `just sf context` re-points `.env` at another
project later.

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
scripts/                     snowflake.py (bootstrap, key-pair setup, check, query), info.py, dbt_all.py
docs/ + mkdocs.yml           the documentation site
overrides/                   Zensical template overrides (page icons in the tabs)
.github/                     CI, release-please, Dependabot, the exported `main` ruleset
```

Data flows KNMI API -> dlt -> `_SRC` (through the internal stage `_SRC.ST_DEFAULT`) -> dbt (`_STG`,
`_INT`, `_MRT`, `_EXP`) inside the project database `DB_EXAMPLE_<ENV>`, with Dagster orchestrating both. In development every engineer
works in personal schemas (`DBT_<USERNAME>_STG`) of the shared `DB_EXAMPLE_DEV`.

## For platform administrators

`terraform/README.md` (also in the docs under *Administration*) walks through the one-time
Snowflake bootstrap (`just setup` on a fresh account, or by hand), the YAML configuration under
`terraform/config`, and onboarding people. Every `just tf plan` shows exactly what changes.

## Working with AI agents

`AGENTS.md` is the canonical instruction set (`CLAUDE.md` is a symlink to it); the docs section
*AI agents* carries the per-technology guides and standards.

## Contributing

See `CONTRIBUTING.md`; security issues go through `SECURITY.md`, never a public issue.

## License

GPL-3.0, see `LICENSE`.
