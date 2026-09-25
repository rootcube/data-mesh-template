---
icon: material/terrain
---

# Environment

Environments are lifecycle isolation stages. They control how data is validated, promoted,
accessed and governed over time. They are not ownership boundaries: every Project has the same
set of Environments, each with a clear purpose.

## The environments

One file per environment under `terraform/config/environments/`:

| Key (file) | `code` | Purpose | `required` | `disabled` | Used by `example` |
|------------|--------|---------|------------|------------|-------------------|
| `development` | `dev` | Rapid iteration and experimentation with light governance | yes | no | yes |
| `test` | `tst` | Automated testing and validation with fixed datasets | no | yes | no |
| `acceptance` | `acc` | Business validation and sign-off in a near-production setup | no | no | no |
| `production` | `prd` | Live data products with stable contracts and strict governance | yes | no | yes |
| `sandbox` | `sbx` | Isolated playground for exploratory analysis and ad-hoc queries | no | yes | no |

```yaml title="terraform/config/environments/development.yaml"
letter: "d"
code: "dev"
name: "Development Environment"
desc: "Rapid iteration and experimentation with light governance"
sort: 100
disabled: false
required: true
```

`disabled: true` hides an environment everywhere: Terraform filters it out of every project
(`terraform/variables.tf`), and the validator warns when a project still lists it. `test` and
`sandbox` ship disabled; enable `test` by flipping the flag and adding it to the project's
`environments`. The example project runs in `development` and `production` only.

## The invariants

The platform states four separations, and the starter implements each one in Snowflake:

| Invariant | Implementation |
|-----------|----------------|
| Separation of compute | A warehouse per environment: `WH_EXAMPLE_DEV`, `WH_EXAMPLE_PRD` |
| Separation of data | A database per environment: `DB_EXAMPLE_DEV`, `DB_EXAMPLE_PRD` |
| Separation of credentials | People use their own key pair; the deployed environments run as service users with their own key pairs |
| Separation of privileges | Human access to production is read-only: `roles/engineer.yaml` grants `SELECT` only in `prd`, writes belong to the transform and ingest system roles |

Changes are promoted forward only, from `dev` towards `prd`, and the same code runs in every
environment. Nothing is copied between environments by hand.

## Development is special

Development is shared: several engineers work in one `DB_EXAMPLE_DEV`. To keep them out of
each other's way, every engineer works in personal schemas named `<SNOWFLAKE_SCHEMA>_<LAYER>`,
for example `DBT_USERNAME_STG`. Terraform creates them for every user who holds the engineer
role in `dev` (the `personal` block in `roles/engineer.yaml`, `environments: [dev]`); dlt and dbt
only use them. The provisioned `_<LAYER>` schemas exist in `dev` too; the other environments use
only those.

The rule is implemented twice, once in Python and once in Jinja, and the dbt source YAML
repeats it with `env_var`:

| Where | Personal (`dev`) | Shared (`tst`, `acc`, `prd`) |
|-------|------------------|------------------------------|
| `SnowflakeSettings.schema_for_layer()` in `src/orchestrator/resources/snowflake.py` | `<SNOWFLAKE_SCHEMA>_<LAYER>` | `_<LAYER>` |
| `dbt_common.generate_schema_name` | `<target.schema>_<LAYER>` | `_<LAYER>` |
| `dbt/dbt_example/sources/src_knmi.yml` | `<SNOWFLAKE_SCHEMA>_SRC` | `_SRC` |

## In the repo

`ENVIRONMENT` in `.env` says which environment a checkout runs as (`dev`, `tst`, `acc` or
`prd`). Three things read it:

- `dbt/profiles.yml`: the target follows `ENVIRONMENT` unless `DBT_TARGET` overrides it. The
  `dev` target uses 8 threads and your personal schema prefix; `tst`, `acc` and `prd` use 16
  threads and the `_<LAYER>` schemas.
- `SnowflakeSettings.from_env()`: `is_personal` is true for `dev` (and for `dummy`), which
  switches the dlt dataset and the Dagster resource to personal schemas.
- `src_knmi.yml`: the source schema expression above.

The rest of the connection (`SNOWFLAKE_ROLE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE`) has to
match the environment: `RL_EXAMPLE_DEV__ENG`, `DB_EXAMPLE_DEV` and `WH_EXAMPLE_DEV` for `dev`.
`just sf setup` writes those for an engineer.

## In Snowflake

The environment `code` is the `<ENV>` segment of every project-scoped name:
`DB_<PROJECT>_<ENV>`, `RL_<PROJECT>_<ENV>__<PURPOSE>`, `WH_<PROJECT>_<ENV>[__<COMPUTE>_<SIZE>]`.
Nothing is shared between two environments of the same project except the account they live in.

Next: [Layer](layer.md).
