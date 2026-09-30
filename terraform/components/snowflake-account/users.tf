# -----------------------------------------------------------------------------
# Users: the persons and service users Terraform creates (config/users/**/*.yaml, keyed by file name)
# -----------------------------------------------------------------------------
# Persons are created here only when `create: true`; existing (SSO) logins just
# receive the grants. Service users (`type: service`) are always created here, with
# the public key of their file. The role grants themselves belong to the project
# stacks (components/snowflake-project/users.tf), one per project and environment,
# which depend on this stack.

locals {
  enabled_users = { for key, user in local.users : key => user if !try(user.disabled, false) }

  users_to_create = { for key, user in local.enabled_users : key => user if try(user.create, false) }

  # Service users (`type: service`): TYPE = SERVICE, a key pair and no password; the deployment
  # runs dlt and dbt as them (terraform/components/dagster).
  services_to_create = { for key, user in local.enabled_users : key => user if try(user.type, "person") == "service" }

  # Every project role a user may assume, over all projects and environments: the defaults of
  # created users and the user_role_grants output. The grants are the project stacks'.
  user_role_grants = flatten([
    for user_key, user in local.enabled_users : [
      for assignment in user.roles : [
        for environment_key in(
          can(tostring(assignment.environments)) && assignment.environments == "*"
          ? local.projects[assignment.project].environments
          : try(tolist(assignment.environments), local.projects[assignment.project].environments)
          ) : {
          user_key       = user_key
          role_name      = upper("RL_${assignment.project}_${local.environment_codes[environment_key]}__${local.role_codes[assignment.role]}")
          database_name  = upper("DB_${assignment.project}_${local.environment_codes[environment_key]}")
          warehouse_name = upper("WH_${assignment.project}_${local.environment_codes[environment_key]}")
        }
        if contains(local.projects[assignment.project].environments, environment_key) &&
        contains(local.projects[assignment.project].roles, assignment.role)
      ]
      if contains(keys(local.projects), assignment.project) && contains(keys(local.roles), assignment.role)
    ]
  ])

  # Defaults for created users: their first role assignment (role, database, default warehouse).
  user_defaults = {
    for user_key in concat(keys(local.users_to_create), keys(local.services_to_create)) :
    user_key => try([for g in local.user_role_grants : g if g.user_key == user_key][0], null)
  }
}

resource "random_password" "user" {
  for_each = local.users_to_create

  length  = 20
  special = false

  # Snowflake's default password policy wants a digit and both cases; without these minimums the
  # generator leaves out a digit about once in fifty and `CREATE USER` is rejected, with the same
  # password re-sent on every retry. Changing them replaces the password of a person already
  # created here, who then gets the new one-time password (README.md, Onboarding a person).
  min_upper   = 1
  min_lower   = 1
  min_numeric = 1
}

resource "snowflake_user" "person" {
  for_each = local.users_to_create
  provider = snowflake.useradmin

  name                 = each.value.login
  email                = try(each.value.email, null)
  comment              = try(each.value.name, each.key)
  password             = random_password.user[each.key].result
  must_change_password = true
  default_role         = try(local.user_defaults[each.key].role_name, null)
  default_warehouse    = try(local.user_defaults[each.key].warehouse_name, null)
  default_namespace    = try(local.user_defaults[each.key].database_name, null)
}

resource "snowflake_service_user" "service" {
  for_each = local.services_to_create
  provider = snowflake.useradmin

  name              = each.value.login
  comment           = try(each.value.name, each.key)
  rsa_public_key    = each.value.rsa_public_key
  default_role      = try(local.user_defaults[each.key].role_name, null)
  default_warehouse = try(local.user_defaults[each.key].warehouse_name, null)
  default_namespace = try(local.user_defaults[each.key].database_name, null)
}

output "user_role_grants" {
  description = "Role grants per user over all projects and environments (login -> roles), from config/users"
  value = {
    for user_key, user in local.enabled_users : user.login => sort([
      for g in local.user_role_grants : g.role_name if g.user_key == user_key
    ])
  }
}

# `just tf output snowflake-account -s account -json initial_passwords` to hand out; each person
# must change it on first login.
output "initial_passwords" {
  description = "One-time passwords of the persons created here (create: true)"
  sensitive   = true
  value       = { for key, pw in random_password.user : local.users_to_create[key].login => pw.result }
}
