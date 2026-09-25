# Snowflake Database Module
#
# Creates a Snowflake database following the platform naming conventions.
# Naming Convention: DB_<PROJECT>_<ENV>

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

locals {
  database_name = upper("DB_${var.project_code}_${var.environment_code}")

  # Conditional Logic, retention based on Environment (prd = 30 days, acc = 7 days, others = 1 day)
  data_retention = var.data_retention_time_in_days != null ? var.data_retention_time_in_days : (
    lower(var.environment_code) == "prd" ? 30 :
    lower(var.environment_code) == "acc" ? 7 :
    1
  )
}

resource "snowflake_database" "this" {
  name                        = local.database_name
  comment                     = var.comment != "" ? var.comment : "Database for Project [${var.project_code}] in [${var.environment_code}] Environment"
  data_retention_time_in_days = local.data_retention
  is_transient                = var.is_transient

  # Removing an environment from a project (or `terraform destroy`) would drop the database with
  # all its data; delete this block deliberately first (README.md, State and teardown).
  lifecycle {
    prevent_destroy = true
  }
}

# Drop the default PUBLIC schema that Snowflake creates automatically
resource "snowflake_execute" "drop_public_schema" {
  execute = "DROP SCHEMA IF EXISTS ${local.database_name}.PUBLIC"
  revert  = "CREATE SCHEMA IF NOT EXISTS ${local.database_name}.PUBLIC"

  depends_on = [snowflake_database.this]
}
