---
icon: material/folder-outline
---

# Project

A Project is a long-lived technical and data ownership boundary. It is owned by exactly one
Team and is the primary unit of isolation for data, compute, credentials and delivery. From a
data mesh perspective, a Project is a **mesh node**: it may produce data products and may
consume data products exposed by other Projects. Everything a Project offers to the outside
goes through its expose layer (`_EXP`), and the owning Team is accountable for it.

A Project is the smallest unit that can independently ingest, transform and expose data, and
deploy that across every Environment.

## What it is, what it is not

A Project is a stable boundary for data and compute ownership, expected to live for years: the
unit of cost attribution and operational accountability, and the isolation boundary for
storage, compute, credentials, roles and code. It is not a temporary experiment (the platform
reserves temporary projects with a time-to-live for that), a single pipeline, an environment,
or a collection of dashboards.

Refactoring inside a Project is normal. Renaming, splitting or merging Projects is a breaking
change, and decommissioning one is an explicit, controlled process.

## In this repo

One file per project under `terraform/config/projects/`. The starter ships `example`:

```yaml title="terraform/config/projects/example.yaml"
team: "platform"
code: "example"
name: "Example Project"
desc: "Starter project: weather observations from the KNMI API"

environments:
  - development
  - production

layers:
  - source
  - reference
  - staging
  - integration
  - mart
  - expose
  - metadata
  - temporary

computes:
  - default

roles:
  - ingest
  - transform
  - engineer
  - analyst
```

The lists hold **keys**, the file names under `environments/`, `layers/`, `computes/` and
`roles/`. The short codes in those files (`dev`, `stg`, `eng`, ...) are what ends up in object
names. Three rules from `terraform/variables.tf`:

Wildcards
:   `"*"` for any of the four lists means every enabled entry of that kind.

Disabled entries are dropped
:   An environment, layer, compute or role with `disabled: true` in its own file is filtered
    out even when a project lists it. `just tf-validate-config` warns about it.

`roles` is authoritative, plus the required ones
:   Only the roles a project lists are created for it; Terraform always adds the roles marked
    `required: true` (`engineer`, `ingest`, `transform`). The validator goes one step further
    and insists that every required entry is listed explicitly: those three roles, the layers
    `source`, `staging` and `expose`, the environments `development` and `production`, and
    the compute `default`.

The project `code` becomes part of every Snowflake name ([Naming](../reference/naming.md)) and
must be lowercase letters, digits and underscores, starting with a letter (checked by the
database module). It must also equal the file name: Terraform names the objects after the file
name (`projects/example.yaml` gives `DB_EXAMPLE_*`), and `just tf-validate-config` rejects a
`code` that differs.

The Project also has a footprint outside `terraform/`:

| Piece | Path | Holds |
|-------|------|-------|
| dbt project | `dbt/dbt_example/` | The models, sources, seeds and tests of this Project |
| Dagster code location | `src/orchestrator/locations/dbt/dbt_example/` | `definitions.py` and `defs/dbt/defs.yaml`; the jobs, freshness schedule and sensor come from `build_dbt_defs()` |
| Workspace entry | `workspace.yaml` | `location_name: "dbt_example"` |

dlt loads live in the shared `dlt_pipelines/` package rather than per project; they land in the
Project database the `SNOWFLAKE_*` variables point at.

## In Snowflake

For every environment the project lists, Terraform creates:

| Object | Name | Example |
|--------|------|---------|
| Database | `DB_<PROJECT>_<ENV>` | `DB_EXAMPLE_DEV`, `DB_EXAMPLE_PRD` |
| One schema per layer | `DB_<PROJECT>_<ENV>._<LAYER>` | `DB_EXAMPLE_DEV._SRC`, `DB_EXAMPLE_DEV._STG`, ... |
| One role per listed role | `RL_<PROJECT>_<ENV>__<PURPOSE>` | `RL_EXAMPLE_DEV__ENG`, `RL_EXAMPLE_PRD__TFM` |
| One warehouse per compute and size | `WH_<PROJECT>_<ENV>[__<COMPUTE>_<SIZE>]` | `WH_EXAMPLE_DEV` |
| Grants | database, schema, warehouse and role-to-role grants per role | `USAGE` on `DB_EXAMPLE_DEV` for every role |

The database module drops the default `PUBLIC` schema, so a project database holds layer
schemas only, plus the personal schemas Terraform creates per engineer in `dev`. Databases
carry `prevent_destroy`: a plan that would drop one, such as removing an environment from the
project, fails until an administrator lifts it
([Snowflake provisioning](../operate/snowflake-provisioning.md)).

Adding a project is copying a folder four times over: the YAML, the dbt project, the Dagster
location and the `workspace.yaml` entry. [Adding a project](../build/adding-projects.md) walks
through it.

Next: [Environment](environment.md).
