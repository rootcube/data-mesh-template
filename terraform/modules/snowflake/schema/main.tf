# Snowflake Schema Module
#
# Creates a Snowflake schema following the platform naming conventions.
# Naming Convention: _<LAYER>, or <PREFIX>_<LAYER> for a developer's personal schema

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

locals {
  schema_name = upper("${var.name_prefix}_${var.layer_code}")
}

resource "snowflake_schema" "this" {
  database = var.database_name
  name     = local.schema_name
  comment  = var.comment != "" ? var.comment : "Schema for Layer [${var.layer_code}] in Database [${var.database_name}]"

  is_transient                = var.is_transient
  with_managed_access         = var.with_managed_access
  data_retention_time_in_days = var.data_retention_time_in_days
}
