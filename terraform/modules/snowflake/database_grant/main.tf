# Snowflake Database Grant Module
#
# Grants privileges on a database to a role.

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "database" {
  account_role_name = var.role_name
  privileges        = var.privileges

  on_account_object {
    object_type = "DATABASE"
    object_name = var.database_name
  }
}
