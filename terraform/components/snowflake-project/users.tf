# -----------------------------------------------------------------------------
# Users: who may assume this project's roles in this environment (config/users/**/*.yaml, keyed by file name)
# -----------------------------------------------------------------------------
# A user lists project roles per environment. The role must exist for that
# project (see the project's `roles`), the environment must be one of the
# project's environments. This stack grants the roles of its own project and
# environment only; the persons with `create: true` and the service users are
# created by the snowflake-account component, which the project stacks depend on
# (terraform/stacks), so they exist before these grants.

locals {
  enabled_users = { for key, user in local.users : key => user if !try(user.disabled, false) }

  # The users the snowflake-account stack creates: persons with `create: true`, and service users.
  users_to_create = {
    for key, user in local.enabled_users : key => user
    if try(user.create, false) || try(user.type, "person") == "service"
  }

  user_role_grants = flatten([
    for user_key, user in local.enabled_users : [
      for assignment in user.roles : [
        for environment_key in(
          can(tostring(assignment.environments)) && assignment.environments == "*"
          ? local.projects[assignment.project].environments
          : try(tolist(assignment.environments), local.projects[assignment.project].environments)
          ) : {
          key       = "${user_key}_${assignment.project}_${environment_key}_${assignment.role}"
          user_key  = user_key
          login     = user.login
          role_name = upper("RL_${assignment.project}_${local.environment_codes[environment_key]}__${local.role_codes[assignment.role]}")
        }
        if contains(local.projects[assignment.project].environments, environment_key) &&
        contains(local.projects[assignment.project].roles, assignment.role)
      ]
      if contains(keys(local.projects), assignment.project) && contains(keys(local.roles), assignment.role)
    ]
  ])

  user_role_grant_map = { for g in local.user_role_grants : g.key => g }

  # The logins this stack grants to that Terraform does not create itself, so the only ones worth
  # checking against the account.
  logins_to_check = toset([for g in local.user_role_grants : g.user_key if !contains(keys(local.users_to_create), g.user_key)])
}

# Every login in the account, so a `create: false` file whose login does not exist here fails at
# plan time with a clear message instead of at apply time with "object does not exist or not
# authorized" (the schemas of that user would already be created by then). SECURITYADMIN holds
# MANAGE GRANTS, so SHOW USERS returns every user. The whole SHOW USERS output lands in the state
# (README.md, Stacks and state), so the read is skipped when this stack has nothing to check; the
# data source takes only a single `like` or `starts_with`, which a list of logins does not fit.
data "snowflake_users" "existing" {
  count           = length(local.logins_to_check) > 0 ? 1 : 0
  provider        = snowflake.securityadmin
  with_describe   = false
  with_parameters = false
}

locals {
  existing_logins = toset(flatten([
    for users in data.snowflake_users.existing : [for user in users.users : upper(user.show_output[0].name)]
  ]))
}

resource "snowflake_grant_account_role" "user" {
  for_each = local.user_role_grant_map
  provider = snowflake.securityadmin

  role_name = each.value.role_name
  user_name = each.value.login

  depends_on = [module.project_role]

  lifecycle {
    precondition {
      condition     = contains(keys(local.users_to_create), each.value.user_key) || contains(local.existing_logins, upper(each.value.login))
      error_message = "User ${each.value.login} (config/users/**/${each.value.user_key}.yaml) does not exist in this account. Set `create: true` to create it, or `disabled: true` if the login belongs to another account."
    }
  }
}
