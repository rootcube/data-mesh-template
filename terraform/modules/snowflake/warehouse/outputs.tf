output "name" {
  description = "The name of the created warehouse"
  value       = snowflake_warehouse.this.name
}

output "id" {
  description = "The ID of the created warehouse"
  value       = snowflake_warehouse.this.id
}

output "project" {
  description = "The project this warehouse belongs to"
  value       = var.project
}

output "environment" {
  description = "The environment of this warehouse"
  value       = var.environment
}

output "profile" {
  description = "The compute profile of this warehouse"
  value       = var.profile
}

output "size" {
  description = "The size of this warehouse"
  value       = var.size
}
