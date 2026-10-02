---
icon: material/server
---

# Compute

Compute is a standardised abstraction for sizing, scaling and isolating execution resources.
The platform defines a small set of reusable compute profiles, each with a type, sizes and
policies, and provisions them per Project × Environment. That keeps workload classes from
interfering with each other and replaces ad-hoc sizing with a few deliberate choices.

A profile is defined once, platform-wide, and instantiated per Project × Environment. Workload
classes do not share compute, so a heavy transformation cannot slow down reporting, and a
workload picks its compute explicitly rather than inheriting it from wherever the code lives.

## The profiles

One file per profile under `terraform/config/computes/`:

| Key (file) | `code` | Purpose | Sizes | Auto-suspend | Clusters | `required` | `disabled` | In `example` |
|------------|--------|---------|-------|--------------|----------|------------|------------|--------------|
| `default` | (none) | General-purpose compute for light ad-hoc usage, development and small tasks | `xs` | 60 s | 1 | yes | no | yes |
| `ingest` | `ing` | Ingestion workloads (extract, load, landing, incremental) | `s`, `m` | 60 s | 1 | no | no | yes |
| `transform` | `tfm` | Transformation workloads (dbt builds, backfills, modelling) | `s`, `m`, `l` | 120 s | 1 | no | no | yes |
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

Size codes map to Snowflake sizes in `terraform/modules/config`: `xs` is `XSMALL`, `s`
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
workload picks the one it needs. The example project lists `default`, `ingest` and `transform`,
so it gets six warehouses per environment: `WH_EXAMPLE_<ENV>`, `WH_EXAMPLE_<ENV>__ING_S` and
`__ING_M`, and `WH_EXAMPLE_<ENV>__TFM_S`, `__TFM_M` and `__TFM_L`.

Roles get warehouse privileges through `privileges.computes` in `roles/*.yaml`:

| Role | Profiles | Privileges |
|------|----------|------------|
| `engineer` | `default`, `ingest`, `transform` | `USAGE`, `OPERATE`, `MONITOR` |
| `analyst` | `default` | `USAGE` |
| `ingest` | `default`, `ingest` | `USAGE`, `OPERATE` |
| `transform` | `default`, `transform` | `USAGE`, `OPERATE` |

Two details of `terraform/components/snowflake-project/main.tf` are worth knowing before you change a project's `computes`:

- A warehouse grant is only created when the project lists that profile. Every shipped role
  asks for `default`, so a project with `computes: [default]` works; the `ingest` and
  `transform` roles additionally ask for their own profiles, which only take effect once the
  project lists them (`example` lists both).
- For a profile with several sizes, a role gets its privileges on **every size**, one warehouse
  each. Which size a workload runs on is the `SNOWFLAKE_WAREHOUSE` it connects with.

The account-level `WH_PLATFORM_PROVISIONING` (X-Small) is the warehouse Terraform itself runs
on, and `WH_PLATFORM` (X-Small, suspended after a minute) the one for the administrators' ad-hoc
queries, the default of whoever ran the bootstrap. Both come from `init.sql`, not from a compute
profile.

## In the repo

`SNOWFLAKE_WAREHOUSE` in `.env` is the warehouse every tool uses: dbt through
`dbt/profiles.yml`, dlt and Python assets through `SnowflakeSettings`. For an engineer that is
`WH_<PROJECT>_DEV`, written by `just sf setup`. There is no per-job warehouse selection yet.
The [Kubernetes deployment](../operate/kubernetes.md) sets it per code location: the first size
of the location's own profile (`dlt` on `WH_<PROJECT>_<ENV>__ING_S`, `dbt-<project>` on
`WH_<PROJECT>_<ENV>__TFM_S`) when the project lists it, `WH_<PROJECT>_<ENV>` otherwise.

That closes the model. How the four tools implement it starts at
[Ingestion](ingestion.md), and every name pattern is on [Naming](../reference/naming.md).
