---
icon: material/domain
---

# Organisation

The Organisation is the highest-level boundary of the platform. It typically corresponds to a
legal, regulatory or financial entity: a company, a holding, a distinct business unit. It is
the global trust boundary, the place where billing, identity, security policy and platform-wide
standards are governed.

## What it is, what it is not

An Organisation **is**:

- the root container for every Team, Project and platform component
- the unit at which compliance, auditing and billing are enforced
- the owner of shared platform funding and standards

An Organisation **is not**:

- a data domain or a mesh node
- a delivery or execution unit
- a substitute for Projects or Teams
- a way of structuring analytical logic

Most setups have exactly one Organisation. A second one only appears when strong separation is
required, such as separate legal entities or external tenants. Teams, Projects and Environments
always belong to exactly one Organisation.

## In this repo

One file, `terraform/config/organisations/example.yaml`:

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

The bootstrap objects that let Terraform manage the account (`TERRAFORM_USER`,
`RL_PLATFORM_PROVISIONING`, `WH_PLATFORM_PROVISIONING`, `DB_PLATFORM_PROVISIONING`) are created
once by `terraform/modules/snowflake/init.sql`, run as `ACCOUNTADMIN`. They belong to the
Organisation level, not to any Project. See
[Snowflake provisioning](../administration/snowflake-provisioning.md).

Next: [Team](team.md).
