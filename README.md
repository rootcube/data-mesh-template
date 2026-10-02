# Data Mesh Platform Starter

A runnable starter for a **data mesh platform on Snowflake**: **Dagster** orchestrates, **dlt**
ingests, **dbt** transforms, **Terraform** provisions. It implements the conceptual model of
[rootcube/platform](https://github.com/rootcube/platform) (Organisation, Team, Project,
Environment, Layer, Role, Compute) in one small repository that runs on a laptop and grows into a
multi-project mesh: one dbt project and one Dagster code location per project, a shared
`dbt_common` package, and YAML-driven Snowflake provisioning.

> Full documentation lives in `docs/` and is served with `just docs` (Zensical). This
> README is the quickstart and a map.
> The published site: <https://rootcube.github.io/data-mesh-template/>.

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

Inside the checkout, `just install <tool>` adds the optional extras: `terraform` and `atmos`
(provisioning; the fresh-account path installs both when missing), `direnv`, `gh`, or `k8s`
(Docker Desktop, k3d and kubectl, for Dagster on Kubernetes); `all` installs `uv`, `terraform`,
`atmos` and `direnv`. Details and alternatives: [Prerequisites](docs/start/prerequisites.md).

### Run

```bash
git clone https://github.com/rootcube/data-mesh-template.git && cd data-mesh-template
just setup       # init, then a one-question wizard (see below), then your .env
just start       # Dagster UI on http://localhost:3000
```

`just setup` runs `just init` and then asks which kind of account this is:

1. **Fresh**, you hold `ACCOUNTADMIN` and nothing is provisioned yet (a free
   [trial](https://signup.snowflake.com/) is enough): it installs Terraform and Atmos if missing,
   creates the Terraform service user, provisions every project (`example` to start with),
   registers your key pair and writes `.env`. It asks for the organization, account name, user
   and password. Step by step: [Snowflake trial account](docs/operate/snowflake-trial-account-setup.md).
2. **Provisioned**, an administrator ran Terraform and granted you a project role: one interactive
   login, your key pair registered on your user, `.env` filled in. Same as `just sf setup`.
3. **Existing**, you hold `ACCOUNTADMIN` and provisioned the account before from another checkout
   or machine: like 1, but it first asks whether to adopt the existing objects into this
   checkout's Terraform states or to drop them, and leaves the account settings alone.
4. **Local only**, no Snowflake account at all: writes `ENVIRONMENT=local` to `.env`, and dlt and
   dbt run against a DuckDB file in the checkout instead. Same as `just sf local`.

`just sf check` proves the key-pair login works; `just sf context` re-points `.env` at another
project later.

Adopting this as your own platform?
[Making it yours](docs/start/adopting.md) covers renaming or removing the example,
taking over the release furniture, and keeping your copy in step with upstream.

Run bare `just` for the full recipe list, or see the docs page *Reference > Commands*.

## What is inside

```
src/orchestrator/            Dagster package
├── locations/dlt/           code location: every dlt ingest pipeline, a job and daily schedule per source and one for all
├── locations/dbt/           shared factory (jobs, source-freshness schedule + sensor) + one code location per dbt project (dbt_example/)
├── resources/snowflake.py   the one place that reads SNOWFLAKE_* and ENVIRONMENT
└── utils/
dlt_pipelines/               dlt package: pipelines/ingest/<source>/ (knmi to start with)
dbt/                         profiles.yml (shared) + dbt_common (package) + dbt_example (project)
terraform/                   Snowflake provisioning from terraform/config, and Dagster on Kubernetes, through Atmos (administrators)
workspace.yaml               the Dagster code locations, for `just start`
Dockerfile                   the code location image of the Kubernetes deployment
scripts/                     snowflake.py (setup wizard, bootstrap, key pairs, check, query, clean), info.py, dbt_all.py,
                             check_asset_keys.py and check_doc_fences.py (checks `just check` runs)
tests/                       pytest, offline only
docs/ + mkdocs.yml           the documentation site; docs/.overrides/ holds the Zensical template overrides (page icons in the tabs)
.github/                     CI, release-please, Dependabot, the exported `main` ruleset
```

Data flows KNMI API -> dlt -> `_SRC` (through the internal stage `_SRC.ST_DEFAULT`) -> dbt (`_STG`,
`_INT`, `_MRT`, `_EXP`) inside the project database `DB_EXAMPLE_<ENV>`, with Dagster orchestrating
both: a daily dlt schedule, an hourly `dbt source freshness` check and a sensor that rebuilds the
downstream of whatever got fresher (stopped in `dev` and `local`, running elsewhere). In
development every engineer works in personal schemas (`DBT_<USERNAME>_SRC` with its own stage,
`DBT_<USERNAME>_STG`, ...) of the shared `DB_EXAMPLE_DEV`, provisioned by Terraform.

## For platform administrators

`terraform/README.md` (also in the docs under *Operate*) walks through the one-time
Snowflake bootstrap (`just setup` on a fresh account, or by hand), the YAML configuration under
`terraform/config`, and onboarding people. Every `just tf plan --all` shows exactly what changes.
*Operate > Dagster on Kubernetes* deploys Dagster to a local k3d cluster: `just install k8s`
(Docker Desktop, k3d, kubectl), `just k8s up`, then `just k8s deploy`. There dlt and dbt run as
Snowflake service users, each on the warehouse of its own compute profile.

## Working with AI agents

`AGENTS.md` is the canonical instruction set (`CLAUDE.md` imports it with a single `@AGENTS.md`
line); the docs page [For AI agents](docs/reference/ai-agents.md) is the entry point into the
per-technology pages under *Understand* and *Reference*.

## Contributing

See `CONTRIBUTING.md`; security issues go through `SECURITY.md`, never a public issue.

## License

GPL-3.0, see `LICENSE`. Third-party code copied into this repository (dbt_artifacts macros, one
Zensical theme partial) stays under its own license: see [`NOTICE`](NOTICE) for the attribution and
`LICENSES/` for the license texts.
