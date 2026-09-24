output "database_name" {
  description = "The database this schema belongs to"
  value       = var.database_name
}

output "layer_code" {
  description = "The layer code of this schema"
  value       = var.layer_code
}

output "schema_id" {
  description = "The ID of the created schema"
  value       = snowflake_schema.this.id
}

output "schema_name" {
  description = "The name of the created schema"
  value       = snowflake_schema.this.name
}

output "fully_qualified_name" {
  description = "The fully qualified name of the schema (DATABASE.SCHEMA)"
  value       = snowflake_schema.this.fully_qualified_name
}
