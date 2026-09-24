# Snowflake Warehouse Module
#
# Creates a Snowflake warehouse following the platform naming conventions.
# Naming Convention: WH_<PROJECT>_<ENV>__<PROFILE>[_<SIZE>]

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

locals {
  # Exclude the size and the profile when Compute is default
  # Use size_code (short code like 'xs', 'm', 'l') in the name, not the full size
  warehouse_name = upper(var.profile == "DEFAULT" ? "WH_${var.project}_${var.environment}" : "WH_${var.project}_${var.environment}__${var.profile}_${var.size_code}")
}

resource "snowflake_warehouse" "this" {
  name           = local.warehouse_name
  warehouse_size = var.size
  comment        = var.comment != "" ? var.comment : "Warehouse for ${var.profile} workloads in ${var.project} ${var.environment}"

  auto_suspend        = var.auto_suspend
  auto_resume         = var.auto_resume
  initially_suspended = var.initially_suspended

  min_cluster_count = var.min_cluster_count
  max_cluster_count = var.max_cluster_count
  scaling_policy    = var.scaling_policy

  resource_monitor = var.resource_monitor

  enable_query_acceleration           = var.enable_query_acceleration
  query_acceleration_max_scale_factor = var.enable_query_acceleration ? var.query_acceleration_max_scale_factor : null
}
