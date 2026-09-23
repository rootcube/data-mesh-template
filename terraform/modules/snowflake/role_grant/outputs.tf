output "role_name" {
  description = "The role that received the grant (child role)"
  value       = var.role_name
}

output "parent_role_name" {
  description = "The role that was granted (parent role)"
  value       = var.parent_role_name
}
