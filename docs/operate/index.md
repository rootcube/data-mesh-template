---
icon: material/shield-account
---

# Operate

For whoever holds the Snowflake account. You turn the mesh described in `terraform/config/` into
databases, schemas, roles and warehouses, and you decide who may assume what. Engineers need none
of it: they get their access from you and then follow [Start](../start/index.md).

- [Snowflake provisioning](snowflake-provisioning.md): the runbook. The one-time account
  bootstrap, the YAML configuration, provider versions, securing the Terraform user, and how to
  tear it all down again.
- [Onboarding](onboarding.md): a person or a service user, from a file under
  `terraform/config/users/` to a working key pair.
- [Snowflake trial account](snowflake-trial-account-setup.md): a fresh account where you hold
  `ACCOUNTADMIN`, bootstrapped and provisioned by `just setup`. The quickest way to watch the
  whole thing run before you commit to it.

Everything is derived from the YAML: a new project is a copy of
`terraform/config/projects/example.yaml` with its own `code`, a new engineer is one more file
under `terraform/config/users/`, and `just tf plan` shows exactly what that becomes before you
apply. Tools: Terraform 1.5 or newer, and the same `just` and uv setup engineers use, since the
YAML validation runs from the repo's virtual environment. `just tf init` pulls the Snowflake
provider at the version pinned in the committed `terraform/.terraform.lock.hcl`. The commands
are listed in [Commands](../reference/commands.md).

## Before the first engineer starts

- [ ] `init.sql` has run as `ACCOUNTADMIN` with the public key of `TERRAFORM_USER` pasted in, and `account_settings.sql` too if you want its account parameters (`just setup` does both on a fresh account; by hand, `just sf keygen terraform` makes the pair and prints the key body)
- [ ] `TERRAFORM_USER` has a network policy and an encrypted key ([Securing the Terraform user](snowflake-provisioning.md#securing-the-terraform-user))
- [ ] The `TF_VAR_SNOWFLAKE_*` block is in your `.env` ([Environment variables](../reference/environment-variables.md))
- [ ] `just tf init`, `just tf-validate-config` and `just tf plan` run clean, then `just tf apply`
- [ ] `just tf output database_names` lists your project's databases, `DB_EXAMPLE_DEV` and `DB_EXAMPLE_PRD` out of the box
- [ ] An `ORGADMIN` accepted the Anaconda terms, or `int__common__holiday` is disabled in the project
- [ ] Every engineer has a `terraform/config/users/<name>.yaml` with the `engineer` role in `development`, applied: that apply creates the personal schemas their first load and build need
- [ ] Every engineer knows the account identifier, their login, `RL_<PROJECT>_DEV__ENG`, `DB_<PROJECT>_DEV` and `WH_<PROJECT>_DEV`
- [ ] You know whether your account lets users set their own `RSA_PUBLIC_KEY`; if not, plan to register keys for them ([Onboarding](onboarding.md#key-registration-fallback))
- [ ] State lives in a remote backend if more than one administrator applies
