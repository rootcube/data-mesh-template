output "project_code" {
  description = "The project this database belongs to"
  value       = var.project_code
}

output "environment_code" {
  description = "The environment of this database"
  value       = var.environment_code
}

output "database_id" {
  description = "The ID of the created database"
  value       = snowflake_database.this.id
}

output "database_name" {
  description = "The name of the created database"
  value       = snowflake_database.this.name
}
