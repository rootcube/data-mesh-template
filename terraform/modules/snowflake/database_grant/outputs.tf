output "role_name" {
  description = "The role that received the grant"
  value       = var.role_name
}

output "database_name" {
  description = "The database the privileges were granted on"
  value       = var.database_name
}

output "privileges" {
  description = "The privileges that were granted"
  value       = var.privileges
}
