# -----------------------------------------------------------------------------
# Users: who may assume which project roles (config/users/*.yaml)
# -----------------------------------------------------------------------------
# A user lists project roles per environment. The role must exist for that
# project (see the project's `roles`), the environment must be one of the
# project's environments. Users are created here only when `create: true`;
# existing (SSO) logins just receive the grants.

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

resource "random_password" "user" {
  for_each = { for key, user in local.users_to_create : key => user if try(user.type, "person") == "person" }

  length  = 20
  special = false
}

resource "snowflake_user" "person" {
  for_each = { for key, user in local.users_to_create : key => user if try(user.type, "person") == "person" }

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
  for_each = { for key, user in local.users_to_create : key => user if try(user.type, "person") == "service" }

  name              = each.value.login
  comment           = try(each.value.name, each.key)
  default_role      = try(local.user_defaults[each.key].role_name, null)
  default_warehouse = try(local.user_defaults[each.key].warehouse_name, null)
  default_namespace = try(local.user_defaults[each.key].database_name, null)
  # Register the public key afterwards: ALTER USER <login> SET RSA_PUBLIC_KEY = '...'
}

resource "snowflake_grant_account_role" "user" {
  for_each = local.user_role_grant_map

  role_name = each.value.role_name
  user_name = each.value.login

  depends_on = [module.project_role, snowflake_user.person, snowflake_service_user.service]
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
