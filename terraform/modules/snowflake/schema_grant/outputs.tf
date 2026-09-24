# =============================================================================
# Schema Grant Module - Outputs
# =============================================================================

output "role_name" {
  description = "The role that received the grants"
  value       = var.role_name
}

output "database_name" {
  description = "The database containing the schema"
  value       = var.database_name
}

output "schema_name" {
  description = "The schema the privileges were granted on"
  value       = var.schema_name
}

output "privileges" {
  description = "The privileges that were granted"
  value       = var.privileges
}

output "schema_privileges" {
  description = "Schema-level privileges that were granted"
  value       = local.schema_privileges
}

output "object_privileges" {
  description = "Object-level privileges that were granted (by object type)"
  value = {
    tables              = local.table_privileges
    views               = local.view_privileges
    materialized_views  = local.materialized_view_privileges
    dynamic_tables      = local.dynamic_table_privileges
    external_tables     = local.external_table_privileges
    iceberg_tables      = local.iceberg_table_privileges
    event_tables        = local.event_table_privileges
    functions           = local.function_privileges
    procedures          = local.procedure_privileges
    stages              = local.stage_privileges
    file_formats        = local.file_format_privileges
    sequences           = local.sequence_privileges
    streams             = local.stream_privileges
    tasks               = local.task_privileges
    pipes               = local.pipe_privileges
    alerts              = local.alert_privileges
    secrets             = local.secret_privileges
    tags                = local.tag_privileges
    masking_policies    = local.masking_policy_privileges
    row_access_policies = local.row_access_policy_privileges
    password_policies   = local.password_policy_privileges
    session_policies    = local.session_policy_privileges
  }
}
