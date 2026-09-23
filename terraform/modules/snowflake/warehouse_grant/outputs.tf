output "role_name" {
  description = "The role that received the grant"
  value       = var.role_name
}

output "warehouse_name" {
  description = "The warehouse the privileges were granted on"
  value       = var.warehouse_name
}

output "privileges" {
  description = "The privileges that were granted"
  value       = var.privileges
}
