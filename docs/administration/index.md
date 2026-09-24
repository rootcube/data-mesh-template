---
icon: material/shield-account
---

# Administration

Pages for **platform administrators**: the people who own the Snowflake account and turn the
mesh described in `terraform/config/` into databases, schemas, roles and warehouses. Engineers
never need any of this; they get their access from you and then follow
[Getting started](../getting-started/index.md).

## What you own

| Concern | Where it lives | Runbook |
|---------|----------------|---------|
| The one-time account bootstrap: `TERRAFORM_USER`, `RL_PLATFORM_PROVISIONING`, `WH_PLATFORM_PROVISIONING`, `DB_PLATFORM_PROVISIONING` and the resource monitor `RM_PLATFORM_PROVISIONING` | `terraform/modules/snowflake/init.sql`, run once as `ACCOUNTADMIN` | [Snowflake provisioning](snowflake-provisioning.md) |
| The mesh: organisation, teams, projects, environments, layers, roles, computes | one YAML file per object under `terraform/config/` | [Snowflake provisioning](snowflake-provisioning.md), [Concepts](../concepts/index.md) |
| Who may assume which project role | `terraform/config/users/<name>.yaml` | [Onboarding](onboarding.md) |
| Key registration for people who cannot set their own key, and for service users | `ALTER USER ... SET RSA_PUBLIC_KEY` | [Onboarding](onboarding.md) |
| Account settings the tooling relies on: the Anaconda terms for Python models | Snowsight, as `ORGADMIN` | [Snowflake provisioning](snowflake-provisioning.md) |
| Terraform state | local `terraform.tfstate` until you move it to a remote backend | [Snowflake provisioning](snowflake-provisioning.md) |
| A test drive on a fresh account: sign-up, MFA, `just setup` | a Snowflake trial | [Snowflake Trial Account setup](snowflake-trial-account-setup.md) |

## How provisioning works

```mermaid
flowchart LR
    YAML["terraform/config/<br/>organisations, teams, projects,<br/>environments, layers, roles,<br/>computes, users"]
    VALIDATE["just tf-validate-config<br/>JSON schemas + cross references"]
    TF["just tf plan / apply<br/>as TERRAFORM_USER"]
    subgraph sf["Snowflake, per project and environment"]
        DB["DB_&lt;PROJECT&gt;_&lt;ENV&gt;"]
        SCH["schemas _SRC, _STG, ..."]
        RL["roles RL_&lt;PROJECT&gt;_&lt;ENV&gt;__&lt;PURPOSE&gt;"]
        WH["warehouses WH_&lt;PROJECT&gt;_&lt;ENV&gt;"]
        GR["grants: role x layer,<br/>role x warehouse, role x user"]
    end
    YAML --> VALIDATE --> TF --> DB & SCH & RL & WH & GR
```

Everything is derived from the YAML. A new project is a copy of
`terraform/config/projects/example.yaml` with its own `code`; a new engineer is a file under
`terraform/config/users/`. `just tf plan` shows exactly what changes before you apply.

## Before the first engineer starts

- [ ] `init.sql` has run as `ACCOUNTADMIN` with the public key of `TERRAFORM_USER` pasted in (`just setup` does this for you on a fresh account; by hand, `just sf keygen terraform` creates the pair and prints the key body)
- [ ] The `TF_VAR_SNOWFLAKE_*` block is in your `.env` (see [Environment variables](../reference/environment-variables.md))
- [ ] `just tf init`, `just tf-validate-config` and `just tf plan` run clean, then `just tf apply`
- [ ] `just tf output database_names` lists `DB_EXAMPLE_DEV` and `DB_EXAMPLE_PRD` (or your own project's databases)
- [ ] An `ORGADMIN` accepted the Anaconda terms, or `int__common__holiday` is disabled in the project
- [ ] Every engineer has a `terraform/config/users/<name>.yaml` with the `engineer` role in `development`, applied
- [ ] Every engineer knows the account identifier, their login, `RL_<PROJECT>_DEV__ENG`, `DB_<PROJECT>_DEV` and `WH_<PROJECT>_DEV`
- [ ] You know whether users may set their own `RSA_PUBLIC_KEY`; if not, plan to register keys for them
- [ ] State lives in a remote backend if more than one administrator applies

## Tools you need

Terraform 1.5 or newer; `just tf init` pulls the Snowflake provider (`snowflakedb/snowflake`
2.x). On top of that, the same `just` and uv setup engineers use (`just init`): the YAML
validation runs from the repo's virtual environment. It is also a pre-commit hook and a CI job,
so a broken configuration never reaches `main`.

## Terraform commands

| Command | What it does |
|---------|--------------|
| `just tf init` | Initialize providers in `terraform/` |
| `just tf-validate-config` | Validate every YAML file under `terraform/config/` against its JSON schema and the cross references |
| `just tf plan` | Show what would change |
| `just tf apply` | Apply it |
| `just tf output database_names` | The databases Terraform manages |
| `just tf output -json user_role_grants` | Which roles each login holds |
| `just tf output -json initial_passwords` | One-time passwords of persons created with `create: true` |
| `just tf destroy` | Remove everything Terraform created; the `init.sql` objects stay |
