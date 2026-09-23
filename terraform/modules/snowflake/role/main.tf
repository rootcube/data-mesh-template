# Snowflake Role Module
#
# Creates a Snowflake role following the platform naming conventions.
# Naming Convention:
#   Project role: ROLE_<PROJECT>_<ENV>__<PURPOSE>
#   Platform role: ROLE__<PURPOSE>

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

locals {
  is_project_role = var.project != "" && var.environment != ""
  role_name       = upper(local.is_project_role ? "RL_${var.project}_${var.environment}__${var.purpose}" : "RL_PLATFORM__${var.purpose}")
}

resource "snowflake_account_role" "this" {
  name    = local.role_name
  comment = var.comment != "" ? var.comment : (local.is_project_role ? "Role for ${var.purpose} in ${var.project} ${var.environment}" : "Platform role for ${var.purpose}")
}

# Grant other roles to this role (role hierarchy - this role inherits permissions)
resource "snowflake_grant_account_role" "inherit" {
  for_each = toset(var.granted_roles)

  role_name        = each.value
  parent_role_name = snowflake_account_role.this.name
}

# Grant this role to other roles (role hierarchy - other roles inherit this role's permissions)
resource "snowflake_grant_account_role" "to_roles" {
  for_each = toset(var.granted_to_roles)

  role_name        = snowflake_account_role.this.name
  parent_role_name = each.value
}

# Grant this role to users
resource "snowflake_grant_account_role" "to_users" {
  for_each = toset(var.granted_to_users)

  role_name = snowflake_account_role.this.name
  user_name = each.value
}
