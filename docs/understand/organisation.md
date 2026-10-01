---
icon: material/domain
---

# Organisation

The Organisation is the highest-level boundary of the platform. It typically corresponds to a
legal, regulatory or financial entity: a company, a holding, a distinct business unit. It is
the global trust boundary, the place where billing, identity, security policy and platform-wide
standards are governed.

## What it is, what it is not

An Organisation is the root container for every Team, Project and platform component, the unit
at which compliance, auditing and billing are enforced, and the owner of shared platform
funding and standards. It is not a data domain, a mesh node, a delivery unit, a substitute for
Projects or Teams, or a way of structuring analytical logic.

Most setups have exactly one. A second one only appears when strong separation is required,
such as separate legal entities or external tenants. Teams, Projects and Environments always
belong to exactly one Organisation.

## In this repo

One file under `terraform/config/organisations/`:

```yaml title="terraform/config/organisations/example.yaml"
code: "EXAMPLE"
name: "Example Organisation"
desc: "Replace with your organisation; the highest-level governance boundary"
```

Teams point at it by file name (`organisation: "example"` in `teams/platform.yaml`), and
`just tf-validate-config` rejects a team whose organisation file does not exist.

## In Snowflake

Terraform creates **no object** for the Organisation. The Snowflake account is the
implementation of this boundary: one account, one Organisation. It is identified everywhere as
`<organization>-<account>`:

| Where | Variable |
|-------|----------|
| Engineers, in `.env` | `SNOWFLAKE_ACCOUNT` (written by `just sf setup`) |
| Administrators, for the Terraform provider | `TF_VAR_SNOWFLAKE_ORGANIZATION` and `TF_VAR_SNOWFLAKE_ACCOUNT` |

The objects that let Terraform manage the account (`TERRAFORM_USER` with the system roles, the
warehouse `WH_PLATFORM_PROVISIONING` and the administrators' `WH_PLATFORM`) are created once by
`terraform/modules/snowflake/init.sql`, run as `ACCOUNTADMIN`, which also sets the account-wide
parameters: UTC, ISO weeks and formats, and the security and timeout defaults. They belong to
the Organisation level, not to any Project. See
[Snowflake provisioning](../operate/snowflake-provisioning.md) and
[Naming](../reference/naming.md).

Next: [Team](team.md).
