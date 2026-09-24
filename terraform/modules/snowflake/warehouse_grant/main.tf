# Snowflake Warehouse Grant Module
#
# Grants privileges on a warehouse to a role.

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "warehouse" {
  account_role_name = var.role_name
  privileges        = var.privileges

  on_account_object {
    object_type = "WAREHOUSE"
    object_name = var.warehouse_name
  }
}
