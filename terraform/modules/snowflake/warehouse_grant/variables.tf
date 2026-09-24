variable "role_name" {
  description = "The name of the role to grant privileges to"
  type        = string

  validation {
    condition     = length(var.role_name) > 0
    error_message = "Role name cannot be empty."
  }
}

variable "warehouse_name" {
  description = "The name of the warehouse to grant privileges on"
  type        = string

  validation {
    condition     = length(var.warehouse_name) > 0
    error_message = "Warehouse name cannot be empty."
  }
}

variable "privileges" {
  description = "List of privileges to grant on the warehouse"
  type        = list(string)

  validation {
    condition     = length(var.privileges) > 0
    error_message = "At least one privilege must be specified."
  }

  validation {
    condition = alltrue([
      for privilege in var.privileges :
      contains(["USAGE", "OPERATE", "MONITOR", "MODIFY", "ALL"], privilege)
    ])
    error_message = "Warehouse privileges must be one of: USAGE, OPERATE, MONITOR, MODIFY, ALL PRIVILEGES."
  }
}
