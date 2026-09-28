# -----------------------------------------------------------------------------
# Users: who may assume which project roles (config/users/**/*.yaml, keyed by file name)
# -----------------------------------------------------------------------------
# A user lists project roles per environment. The role must exist for that
# project (see the project's `roles`), the environment must be one of the
# project's environments. Persons are created here only when `create: true`;
# existing (SSO) logins just receive the grants. Service users for the system
# roles are created by hand with a key pair (see README.md).

locals {
  enabled_users = { for key, user in local.users : key => user if !try(user.disabled, false) }

  users_to_create = { for key, user in local.enabled_users : key => user if try(user.create, false) }

  user_role_grants = flatten([
    for user_key, user in local.enabled_users : [
      for assignment in user.roles : [
        for environment_key in(
          can(tostring(assignment.environments)) && assignment.environments == "*"
          ? local.projects[assignment.project].environments
          : try(tolist(assignment.environments), local.projects[assignment.project].environments)
          ) : {
          key            = "${user_key}_${assignment.project}_${environment_key}_${assignment.role}"
          user_key       = user_key
          login          = user.login
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

  user_role_grant_map = { for g in local.user_role_grants : g.key => g }

  # Defaults for created users: their first role assignment (role, database, default warehouse).
  user_defaults = {
    for user_key in keys(local.users_to_create) :
    user_key => try([for g in local.user_role_grants : g if g.user_key == user_key][0], null)
  }
}

# Every login in the account, so a `create: false` file whose login does not exist here fails at
# plan time with a clear message instead of at apply time with "object does not exist or not
# authorized" (the schemas of that user would already be created by then). SECURITYADMIN holds
# MANAGE GRANTS, so SHOW USERS returns every user.
data "snowflake_users" "existing" {
  provider        = snowflake.securityadmin
  with_describe   = false
  with_parameters = false
}

locals {
  existing_logins = toset([for user in data.snowflake_users.existing.users : upper(user.show_output[0].name)])
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

resource "snowflake_grant_account_role" "user" {
  for_each = local.user_role_grant_map
  provider = snowflake.securityadmin

  role_name = each.value.role_name
  user_name = each.value.login

  depends_on = [module.project_role, snowflake_user.person]

  lifecycle {
    precondition {
      condition     = contains(keys(local.users_to_create), each.value.user_key) || contains(local.existing_logins, upper(each.value.login))
      error_message = "User ${each.value.login} (config/users/**/${each.value.user_key}.yaml) does not exist in this account. Set `create: true` to create it, or `disabled: true` if the login belongs to another account."
    }
  }
}

output "user_role_grants" {
  description = "Role grants per user (login -> roles)"
  value = {
    for user_key, user in local.enabled_users : user.login => sort([
      for g in local.user_role_grants : g.role_name if g.user_key == user_key
    ])
  }
}

# `just tf output -json initial_passwords` to hand out; each person must change it on first login.
output "initial_passwords" {
  description = "One-time passwords of the persons created here (create: true)"
  sensitive   = true
  value       = { for key, pw in random_password.user : local.users_to_create[key].login => pw.result }
}
