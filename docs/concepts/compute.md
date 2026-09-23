---
icon: material/server
---

# Compute

Compute is a standardised abstraction for sizing, scaling and isolating execution resources.
The platform defines a small set of reusable compute profiles, each with a type, sizes and
policies, and provisions them per Project × Environment. That keeps workload classes from
interfering with each other, makes cost attributable per project and environment, and replaces
ad-hoc sizing with a few deliberate choices.

Principles:

- Profiles are defined once, platform-wide, and reused consistently.
- Instances are provisioned per Project × Environment.
- Workload classes do not share compute: a heavy transformation must not slow down reporting.
- Compute is selected explicitly per workload, not implied by where the code lives.

## The profiles

One file per profile under `terraform/config/computes/`:

| Key (file) | `code` | Purpose | Sizes | Auto-suspend | Clusters | `required` | `disabled` | In `example` |
|------------|--------|---------|-------|--------------|----------|------------|------------|--------------|
| `default` | (none) | General-purpose compute for light ad-hoc usage, development and small tasks | `xs` | 60 s | 1 | yes | no | yes |
| `ingest` | `ing` | Ingestion workloads (extract, load, landing, incremental) | `s`, `m` | 60 s | 1 | no | no | no |
| `transform` | `tfm` | Transformation workloads (dbt builds, backfills, modelling) | `s`, `m`, `l` | 120 s | 1 | no | no | no |
| `analysis` | `anl` | Exploratory analysis and interactive workloads | `s`, `m` | 60 s | 1 to 2 | no | yes | no |
| `reporting` | `rpt` | BI and consumption workloads needing stable performance | `s`, `m` | 300 s | 1 to 2 | no | yes | no |

```yaml title="terraform/config/computes/default.yaml"
code: "" # Default will not use code suffix
name: "Default"
desc: "General-purpose compute for light ad-hoc usage, development, and small tasks"
disabled: false
required: true

sizes:
  - xs

auto_suspend: 60
auto_resume: true
min_cluster_count: 1
max_cluster_count: 1
```

Size codes map to Snowflake sizes in `terraform/variables.tf`: `xs` is `XSMALL`, `s`
`SMALL`, `m` `MEDIUM`, `l` `LARGE`, `xl` `XLARGE`, and so on up to `x6l`. Every warehouse is
created suspended (the module default) and resumes on first use.

## In Snowflake

For every project, environment, listed compute and size, Terraform creates one warehouse:

| Profile | Name | Example |
|---------|------|---------|
| `default` | `WH_<PROJECT>_<ENV>` | `WH_EXAMPLE_DEV`, `WH_EXAMPLE_PRD` |
| any other | `WH_<PROJECT>_<ENV>__<COMPUTE>_<SIZE>` | `WH_EXAMPLE_PRD__TFM_M`, `WH_EXAMPLE_PRD__ING_S` |

The `default` profile carries no suffix, so every project always has a plain
`WH_<PROJECT>_<ENV>`. A profile with three sizes produces three warehouses, one per size, and a
workload picks the one it needs. The example project lists `default` only, so it gets exactly
`WH_EXAMPLE_DEV` and `WH_EXAMPLE_PRD`.

Roles get warehouse privileges through `privileges.computes` in `roles/*.yaml`:

| Role | Profiles | Privileges |
|------|----------|------------|
| `engineer` | `default`, `ingest`, `transform` | `USAGE`, `OPERATE`, `MONITOR` |
| `analyst` | `default` | `USAGE` |
| `ingest` | `ingest` | `USAGE`, `OPERATE` |
| `transform` | `transform` | `USAGE`, `OPERATE` |

Two details of `terraform/main.tf` are worth knowing before you change a project's `computes`:

- A warehouse grant is only created when the project lists that profile. Every shipped role
  asks for `default`, so a project with `computes: [default]` works; the `ingest` and
  `transform` roles additionally ask for their own profiles, which only take effect once the
  project lists them.
- For a profile with several sizes, the grant goes to the **first listed size** only
  (`sizes[0]`). Put the size you want the role to use first, or grant the others by hand.

The account-level `WH_PLATFORM_PROVISIONING` (X-Small, resource monitor
`RM_PLATFORM_PROVISIONING`) is the warehouse Terraform itself runs on. It comes from
`init.sql`, not from a compute profile.

## In the repo

`SNOWFLAKE_WAREHOUSE` in `.env` is the warehouse every tool uses: dbt through
`dbt/profiles.yml`, dlt through `SnowflakeSettings.dlt_credentials()`, Python assets through
`SnowflakeSettings.connect()`. For an engineer that is
`WH_<PROJECT>_DEV`, written by `just snowflake setup`. There is no per-job warehouse selection
yet; when a project adds the `transform` profile, pointing dbt at `WH_<PROJECT>_<ENV>__TFM_M`
is a change of that one variable in the deployed environment.

Back to the [Concepts overview](index.md), or on to how the tools implement all of this:
[Architecture](../architecture/index.md).
