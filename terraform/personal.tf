# -----------------------------------------------------------------------------
# Personal schemas: every developer's own copy of the project layers
# -----------------------------------------------------------------------------
# A role with a `personal` block (config/roles/engineer.yaml) gives each user who
# holds it (config/users) a schema per project layer in the listed environments:
# <PREFIX>_SRC, <PREFIX>_STG, ... in DB_<PROJECT>_DEV. They are created here, owned by
# SYSADMIN like every other schema, and the role gets the block's privileges on them;
# stages.tf adds the user's own load stage <PREFIX>_SRC.ST_DEFAULT.
#
# <PREFIX> is the user's `schema_prefix`, or DBT_<login before the @> with every run of
# non-alphanumerics as `_`, upper case (DBT_USERNAME for username@example.com): the
# same rule as personal_prefix() in scripts/snowflake.py, which writes it to .env as
# SNOWFLAKE_SCHEMA for dlt and dbt.

locals {
  # One entry per user x project x environment x role that comes with personal schemas.
  personal_assignments = flatten([
    for user_key, user in local.enabled_users : [
      for assignment in user.roles : [
        for environment_key in(
          can(tostring(assignment.environments)) && assignment.environments == "*"
          ? local.projects[assignment.project].environments
          : try(tolist(assignment.environments), local.projects[assignment.project].environments)
          ) : {
          user_key        = user_key
          login           = user.login
          prefix          = try(user.schema_prefix, "DBT_${upper(trim(replace(split("@", user.login)[0], "/[^A-Za-z0-9]+/", "_"), "_"))}")
          project_key     = assignment.project
          environment_key = environment_key
          database_name   = upper("DB_${assignment.project}_${local.environment_codes[environment_key]}")
          role_key        = assignment.role
          role_name       = upper("RL_${assignment.project}_${local.environment_codes[environment_key]}__${local.role_codes[assignment.role]}")
          privileges      = try(local.roles[assignment.role].personal.privileges, [])
        }
        if contains(local.projects[assignment.project].environments, environment_key) &&
        contains(local.projects[assignment.project].roles, assignment.role) &&
        contains(try(local.roles[assignment.role].personal.environments, []), local.environment_codes[environment_key])
      ]
      if contains(keys(local.projects), assignment.project) && contains(keys(local.roles), assignment.role)
    ]
  ])

  # Schemas: user x project x environment x layer (several roles share one set of schemas).
  personal_schema_map = merge([
    for a in local.personal_assignments : {
      for layer_key in local.projects[a.project_key].layers :
      "${a.user_key}_${a.project_key}_${a.environment_key}_${layer_key}" => {
        user_key        = a.user_key
        login           = a.login
        prefix          = a.prefix
        project_key     = a.project_key
        environment_key = a.environment_key
        database_name   = a.database_name
        layer_key       = layer_key
        layer_code      = local.layer_codes[layer_key]
      }
    }
  ]...)

  # Grants: one per schema and role.
  personal_schema_grant_map = merge([
    for a in local.personal_assignments : {
      for layer_key in local.projects[a.project_key].layers :
      "${a.user_key}_${a.project_key}_${a.environment_key}_${layer_key}_${a.role_key}" => {
        schema_key    = "${a.user_key}_${a.project_key}_${a.environment_key}_${layer_key}"
        role_name     = a.role_name
        database_name = a.database_name
        schema_name   = upper("${a.prefix}_${local.layer_codes[layer_key]}")
        privileges    = a.privileges
      }
    }
  ]...)
}

module "personal_schema" {
  source   = "./modules/snowflake/schema"
  for_each = local.personal_schema_map

  database_name = each.value.database_name
  name_prefix   = each.value.prefix
  layer_code    = each.value.layer_code
  comment       = "Personal ${each.value.layer_key} schema of ${each.value.login}"

  depends_on = [module.database]
}

module "personal_schema_grant" {
  source    = "./modules/snowflake/schema_grant"
  for_each  = local.personal_schema_grant_map
  providers = { snowflake = snowflake.securityadmin }

  role_name     = each.value.role_name
  database_name = each.value.database_name
  schema_name   = module.personal_schema[each.value.schema_key].schema_name
  privileges    = each.value.privileges

  depends_on = [module.project_role]
}

output "personal_schemas" {
  description = "Personal schemas per user (login -> fully qualified schema names)"
  value = {
    for login in distinct([for s in local.personal_schema_map : s.login]) : login => sort([
      for key, s in local.personal_schema_map : module.personal_schema[key].fully_qualified_name if s.login == login
    ])
  }
}
