variable "role_name" {
  description = "The name of the role that will inherit permissions (child role)"
  type        = string

  validation {
    condition     = length(var.role_name) > 0
    error_message = "Role name cannot be empty."
  }
}

variable "parent_role_name" {
  description = "The name of the role to inherit from (parent role)"
  type        = string

  validation {
    condition     = length(var.parent_role_name) > 0
    error_message = "Parent role name cannot be empty."
  }
}
