# Snowflake Role Grant Module
#
# Grants role inheritance - allows one role to inherit permissions from another.
# This establishes role hierarchy in Snowflake.

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

# Grant the parent role to the child role (child inherits parent's permissions)
resource "snowflake_grant_account_role" "inherit" {
  role_name        = var.parent_role_name
  parent_role_name = var.role_name
}
