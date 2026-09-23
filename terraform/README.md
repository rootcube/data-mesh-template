# Snowflake provisioning

Terraform turns the YAML under `config/` into Snowflake objects, following the platform's
conceptual model: **Organisation** > **Team** > **Project** > **Environment** > { **Layers**,
**Roles**, **Computes** }, plus **Users** who may assume project roles. Only platform
administrators run this; engineers never need Terraform.

## What one project becomes

For every project and each of its environments (`config/projects/<project>.yaml`):

| Concept | Snowflake object | Example |
|---------|------------------|---------|
| Project × Environment | database `DB_<PROJECT>_<ENV>` | `DB_EXAMPLE_DEV`, `DB_EXAMPLE_PRD` |
| Layer | schema `_<LAYER>` in that database | `_SRC`, `_STG`, `_INT`, `_MRT`, `_EXP`, `_REF`, `_MTD`, `_TMP` |
| Role | account role `RL_<PROJECT>_<ENV>__<PURPOSE>` with grants per layer | `RL_EXAMPLE_DEV__ENG`, `RL_EXAMPLE_PRD__TFM` |
| Compute | warehouse `WH_<PROJECT>_<ENV>[__<COMPUTE>_<SIZE>]` | `WH_EXAMPLE_DEV` |
| User | role grants (and optionally the user itself) | `engineer@example.com` gets `RL_EXAMPLE_DEV__ENG` |

Development is shared: engineers hold `CREATE SCHEMA` on `DB_<PROJECT>_DEV` and work in personal
schemas `<PREFIX>_<LAYER>` (for example `DBT_INFO_STG`), which dlt and dbt create on demand. The
other environments only use the provisioned `_<LAYER>` schemas.

## One-time bootstrap

1. Generate a key pair for the Terraform service user; the command prints the public key body:

    ```bash
    just snowflake keygen terraform
    ```

2. Open `modules/snowflake/init.sql`, uncomment the `RSA_PUBLIC_KEY` line in the `ALTER USER`
   block of `TERRAFORM_USER` and paste the public key body, then run the whole script as
   `ACCOUNTADMIN` in Snowsight. It creates `TERRAFORM_USER`, the role `RL_PLATFORM_PROVISIONING`
   (with usage on the provisioning warehouse and database), the warehouse
   `WH_PLATFORM_PROVISIONING`, the database `DB_PLATFORM_PROVISIONING` and a resource monitor.
   The script is idempotent; rerun it after edits. If the user already holds a key in
   `RSA_PUBLIC_KEY` (another administrator's machine), use `RSA_PUBLIC_KEY_2` for the second one.

3. Put the provider settings in `.env` (the block at the bottom of `.env.example`):

    ```dotenv
    TF_VAR_SNOWFLAKE_ORGANIZATION=<organization>
    TF_VAR_SNOWFLAKE_ACCOUNT=<account>
    TF_VAR_SNOWFLAKE_USER=TERRAFORM_USER
    TF_VAR_SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/terraform.p8
    ```

4. Initialize and check the configuration:

    ```bash
    just tf init
    just tf-validate-config
    just tf plan
    ```

## Configuration

One YAML file per object, validated against the JSON schemas in `config/_validation/schemas/`
(`just tf-validate-config`, also a pre-commit hook and a CI step).

| Folder | Holds | Notes |
|--------|-------|-------|
| `organisations/` | the organisation | one file |
| `teams/` | teams that own projects | `organisation` refers to the organisation file name |
| `projects/` | one file per project | `team`, `environments`, `layers`, `computes`, `roles`; `"*"` means all enabled |
| `environments/` | dev, tst, acc, prd (and sandbox) | `disabled: true` hides an environment everywhere |
| `layers/` | source, reference, staging, integration, mart, expose, metadata, temporary, ... | codes become schema names |
| `roles/` | project roles (engineer, analyst, ingest, transform) and global roles | privileges per compute, database, layer and environment |
| `computes/` | warehouse profiles and sizes | `default` has no suffix |
| `users/` | who may assume which project roles | see onboarding below |

A new project is a copy of `projects/example.yaml` with its own `code`; `just tf plan` shows the
databases, schemas, roles and warehouses it adds.

## Onboarding a person

1. Add `config/users/<name>.yaml`:

    ```yaml
    login: "someone@example.com"
    name: "Someone"
    type: "person"
    create: false        # true creates the user with a one-time password
    roles:
      - project: example
        role: engineer
        environments: [development]
    ```

2. `just tf apply`. For created users, hand out the password from
   `just tf output -json initial_passwords`.

3. The person runs `just snowflake setup`, which logs in once, registers a key pair and writes
   their `.env` with `SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG`, `SNOWFLAKE_DATABASE=DB_EXAMPLE_DEV`,
   `SNOWFLAKE_WAREHOUSE=WH_EXAMPLE_DEV` and a personal schema prefix such as `DBT_SOMEONE`.

System users for deployed environments (the transform and ingest roles) are created by hand:
`CREATE USER <login> TYPE = SERVICE`, then `just snowflake keygen <login>` and
`ALTER USER <login> SET RSA_PUBLIC_KEY = '...'`. Grant them `RL_<PROJECT>_<ENV>__TFM` or
`__ING` through a `create: false` user file with the same `roles` list.

!!! note "If a person cannot register their own key"
    `ALTER USER ... SET RSA_PUBLIC_KEY` on your own user is allowed by default. If an account
    policy blocks it, register the `.pub` file for them as `SECURITYADMIN`.

## Differences from rootcube/platform

This folder is a port of the platform repository's Terraform with three additions, kept small
so they can flow back upstream:

- `config/users/` and `users.tf`: role grants to logins (and optional user creation).
- `privileges.database` on a role: extra database privileges per environment on top of the
  implicit `USAGE` (engineers get `CREATE SCHEMA` in dev for their personal schemas).
- `config/layers/metadata.yaml` (`_MTD`): where dbt writes run metadata.

The provider is Snowflake only; the dbt Cloud, GitHub and Kubernetes providers of the platform
repository are not part of the starter.

## Python models need Anaconda packages

`dbt_common` ships a Python (Snowpark) model, `int__generic__holiday`, that imports the
`holidays` package from the Snowflake Anaconda channel. An `ORGADMIN` accepts the Anaconda terms
once per account (Snowsight: Admin > Billing & Terms). Without that, disable the model in the
consuming project:

```yaml
models:
  dbt_common:
    03_int:
      generic:
        int__generic__holiday:
          +enabled: false
```

## State and teardown

State is local (`terraform.tfstate`, git-ignored). Move it to a remote backend before several
administrators share the configuration. `just tf destroy` removes everything Terraform created;
the bootstrap objects from `init.sql` stay.
