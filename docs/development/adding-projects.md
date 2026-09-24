---
icon: material/folder-plus
---

# Adding a project

A project is a node in the mesh: one team owns it, it exists in environments, and each
project × environment is its own Snowflake database with layer schemas, roles and warehouses.
In the repository a project is one dbt project under `dbt/` and one Dagster code location; every
project shares the `dbt_common` package, the `dlt` location and the tooling. The starter ships
`example`; this page adds a second one end to end. Background: [Project](../concepts/project.md),
[Transformation](../architecture/transformation.md), [Orchestration](../architecture/orchestration.md).

Two personas are involved. A **platform administrator** provisions Snowflake with Terraform
(steps 1 and 2); an **engineer** does the rest. Throughout, `<project>` is the lowercase code
from the YAML (`energy` in the examples), `<PROJECT>` the same in uppercase inside Snowflake
names (`DB_ENERGY_DEV`), and `dbt_<project>` the dbt project and code location (`dbt_energy`).

## 1. Describe the project (administrator)

Copy `terraform/config/projects/example.yaml` to `terraform/config/projects/<project>.yaml` and
give it its own `code`, `name` and `desc`:

```yaml title="terraform/config/projects/energy.yaml"
# yaml-language-server: $schema=../_validation/schemas/project.schema.json
# Project: Energy
# ===============

team: "platform"
code: "energy"
name: "Energy Project"
desc: "Energy consumption and generation, built on the KNMI weather data"

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

Every list entry is a file name under `terraform/config/` (`environments/development.yaml`,
`layers/source.yaml`, `computes/default.yaml`, `roles/engineer.yaml`); `"*"` means every enabled
one. `team` is a file under `teams/`. `code` is lowercase, 2 to 20 characters, letters, digits
and underscores, and becomes the `<PROJECT>` part of every Snowflake name.

Validate the YAML (schemas plus cross-references), then plan and apply:

```bash
just tf-validate-config
just tf plan
just tf apply
```

The plan lists what one project becomes:

| Concept | Snowflake object | For `energy` |
|---|---|---|
| Project × Environment | database `DB_<PROJECT>_<ENV>` | `DB_ENERGY_DEV`, `DB_ENERGY_PRD` |
| Layer | schema `_<LAYER>` in that database | `_SRC`, `_REF`, `_STG`, `_INT`, `_MRT`, `_EXP`, `_MTD`, `_TMP` |
| Role | account role `RL_<PROJECT>_<ENV>__<PURPOSE>` | `RL_ENERGY_DEV__ENG`, `RL_ENERGY_DEV__ANL`, `RL_ENERGY_PRD__ING`, `RL_ENERGY_PRD__TFM` |
| Compute | warehouse `WH_<PROJECT>_<ENV>` | `WH_ENERGY_DEV`, `WH_ENERGY_PRD` |

`just tf-validate-config` is also a pre-commit hook and a CI step, so the YAML is checked on
every pull request; only `plan` and `apply` need the Terraform service user. Details:
[Snowflake provisioning](../administration/snowflake-provisioning.md).

## 2. Give people the engineer role (administrator)

Users assume project roles. Add the project to each engineer's file under
`terraform/config/users/` and apply again:

```yaml title="terraform/config/users/username.yaml"
login: "username@example.com"
name: "Username"
type: "person"
create: false
roles:
  - project: example
    role: engineer
    environments:
      - development
  - project: energy
    role: engineer
    environments:
      - development
```

That grants `RL_ENERGY_DEV__ENG`, which carries `CREATE SCHEMA` on `DB_ENERGY_DEV` for the
personal schemas. See [Onboarding](../administration/onboarding.md).

## 3. Copy the dbt project (engineer)

Copy `dbt/dbt_example` to `dbt/dbt_<project>`. The git-ignored `target/`, `packages/` and
`logs/` folders do not need to come along. `.sqlfluff` and `.sqlfluffignore` live one level up in
`dbt/` and already apply to every project. Then edit `dbt_project.yml`:

```yaml title="dbt/dbt_energy/dbt_project.yml (the parts that change)"
name: "dbt_energy"

# unchanged: profile "default", require-dbt-version, paths, packages-install-path, dispatch

models:
  dbt_energy:                   # was dbt_example
    +materialized: view
    +persist_docs:
      relation: true
      columns: true

    02_stg:
      +schema: stg
      +materialized: table
      +tags: ["layer=stg"]
    # 03_int, 04_mrt, 05_exp unchanged

  # dbt_example builds the shared dbt_common models; this project only uses the macros.
  dbt_common:
    +enabled: false             # was true

seeds:
  dbt_energy:                   # was dbt_example
    +schema: ref
```

Three things matter here:

The `name`
:   It is the dbt package name, the first segment of every asset key and group, and part of the
    asset job name.

`dbt_common: +enabled: false`
:   Every project installs `dbt_common`, but exactly one builds its models. Two projects building
    `dim__common__calendar` get distinct asset keys (`<project>/packages/dbt_common/...`) but
    write the same table into the one database `.env` points at. The macros, the dispatch
    overrides and the `on-run-start` / `on-run-end` hooks keep working with the models disabled.

The dispatch block stays
:   Without `search_order: ["dbt_common", "dbt"]` the project falls back to dbt's own
    `generate_schema_name`, which in the shared environments builds into `_TMP_STG` (the
    profile's default schema plus the layer) instead of the provisioned `_STG`.

`packages.yml` is the same file in every project: the local `../dbt_common` plus `dbt_utils`.
Delete the copied `sources/src_knmi.yml` and `models/02_stg/knmi/` unless this project owns
that source. Asset keys carry the project name (`dbt_energy/models/...`), so a model name only has to be
unique within its project.

Install the packages for the new project:

```bash
just dbt-all deps
```

`scripts/dbt_all.py` finds every `dbt/*/dbt_project.yml` except `dbt_common`, so from now on
`just init`, the pre-commit parse hook and CI's parse step include the new project without
further changes.

## 4. Copy the Dagster location (engineer)

Copy `src/orchestrator/locations/dbt/dbt_example` to
`src/orchestrator/locations/dbt/dbt_<project>`. Two files change.

```python title="src/orchestrator/locations/dbt/dbt_energy/definitions.py"
"""Dagster code location for the dbt_energy project (see locations/dbt/shared.py)."""

from orchestrator.locations.dbt.dbt_energy import defs as _defs_module
from orchestrator.locations.dbt.shared import build_dbt_defs

defs = build_dbt_defs("dbt_energy", _defs_module)
```

```yaml title="src/orchestrator/locations/dbt/dbt_energy/defs/dbt/defs.yaml"
type: orchestrator.locations.dbt.shared.DataMeshDbtProjectComponent

attributes:
  project:
    project_dir: '{{ context.project_root }}/dbt/dbt_energy'
    profiles_dir: '{{ context.project_root }}/dbt'
    prepare_project_cli_args: ["parse", "--quiet"]
  select: "*"
```

`build_dbt_defs()` gives the location `job_dbt_energy_build_all` for free.

## 5. Register the location (engineer)

`workspace.yaml` is the authoritative list of code locations. Add one block:

```yaml title="workspace.yaml (excerpt)"
  - python_module:
      module_name: orchestrator.locations.dbt.dbt_energy.definitions
      location_name: "dbt_energy"
```

## 6. Point your `.env` at the project and build (engineer)

Your `.env` selects the project you work in. Three lines change:

```dotenv
SNOWFLAKE_ROLE=RL_ENERGY_DEV__ENG
SNOWFLAKE_WAREHOUSE=WH_ENERGY_DEV
SNOWFLAKE_DATABASE=DB_ENERGY_DEV
```

`SNOWFLAKE_SCHEMA` (your personal prefix) and the key pair stay as they are: the same key works
in every project you hold a role in. `just sf check` confirms the context and prints the
layer schemas (`DBT_<USERNAME>_SRC, DBT_<USERNAME>_STG, ...`).

Then:

```bash
just project=dbt_energy dbt parse --target dummy   # no connection, catches config mistakes
just project=dbt_energy dbt build                  # your personal schemas in DB_ENERGY_DEV
just validate                                      # every location loads, the new one included
just start                                         # one more location in the UI
```

The `project=` override works for every recipe that runs in the project folder:
`just project=dbt_energy sqlfluff lint models`, `just project=dbt_energy lint`,
`just project=dbt_energy fmt`. Without it, `just dbt` targets `dbt_example`.

Everything `just start` runs uses the database in your `.env`, so work on one project at a time
and switch `.env` to move. The locations of other projects still load (parsing never connects).

## Sharing data between projects

With `dbt_common` disabled, `ref('dim__common__calendar')` does not resolve in the new project,
and the tables `dbt_example` builds live in `DB_EXAMPLE_<ENV>`, not in yours. That is the point
of the mesh: a project publishes through its `_EXP` layer and other projects read that contract
(the `import` layer under `terraform/config/layers/` exists for received contracts). The starter
provisions no cross-project grants, so reading another project's `_EXP` is an administrator's
decision in `terraform/config/roles/`. See [Layer](../concepts/layer.md) and
[Layers in practice](../architecture/layers.md).

## What stays per project

Two checks are wired to `dbt_example` by path and need an extra line for the new project if you
want the same coverage:

- The `sqlfluff-lint` hook in `.pre-commit-config.yaml` and the sqlfluff step in
  `.github/workflows/ci.yml` both `cd dbt/dbt_example`.
- `just fmt` and `just lint` run sqlfluff in the project selected by `project=`; the default is
  `dbt_example`.

The dbt parse hook and CI's parse step already cover every project through `dbt_all.py`, and
`dagster definitions validate -w workspace.yaml` loads every location.

## Checklist

Administrator:

- [ ] `terraform/config/projects/<project>.yaml` with its own `code`; `just tf-validate-config` passes
- [ ] `just tf apply` created `DB_<PROJECT>_<ENV>`, the layer schemas, the roles and the warehouse
- [ ] Engineers hold `RL_<PROJECT>_DEV__ENG` through `terraform/config/users/`

Engineer:

- [ ] `dbt/dbt_<project>/dbt_project.yml`: `name`, the `models:` and `seeds:` keys, `dbt_common: +enabled: false`, dispatch block kept
- [ ] `packages.yml` unchanged (`../dbt_common` + `dbt_utils`); `just dbt-all deps` ran
- [ ] `src/orchestrator/locations/dbt/dbt_<project>/definitions.py` and `defs/dbt/defs.yaml` point at the new project
- [ ] `workspace.yaml` lists `dbt_<project>`
- [ ] `.env` points at `DB_<PROJECT>_DEV`, `RL_<PROJECT>_DEV__ENG`, `WH_<PROJECT>_DEV`
- [ ] `just project=dbt_<project> dbt build`, `just validate` and `just check` pass
- [ ] Model names do not collide with other projects
