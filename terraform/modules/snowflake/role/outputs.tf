output "name" {
  description = "The name of the created role"
  value       = snowflake_account_role.this.name
}

output "id" {
  description = "The ID of the created role"
  value       = snowflake_account_role.this.id
}

output "is_project_role" {
  description = "Whether this is a project-level role"
  value       = local.is_project_role
}

output "project" {
  description = "The project this role belongs to (empty for platform roles)"
  value       = var.project
}

output "environment" {
  description = "The environment of this role (empty for platform roles)"
  value       = var.environment
}

output "purpose" {
  description = "The purpose/type of this role"
  value       = var.purpose
}
