variable "role_name" {
  description = "The name of the role to grant privileges to"
  type        = string

  validation {
    condition     = length(var.role_name) > 0
    error_message = "Role name cannot be empty."
  }
}

variable "database_name" {
  description = "The name of the database to grant privileges on"
  type        = string

  validation {
    condition     = length(var.database_name) > 0
    error_message = "Database name cannot be empty."
  }
}

variable "privileges" {
  description = "List of privileges to grant on the database"
  type        = list(string)

  validation {
    condition     = length(var.privileges) > 0
    error_message = "At least one privilege must be specified."
  }

  validation {
    condition = alltrue([
      for priv in var.privileges :
      contains(["USAGE", "MONITOR", "CREATE SCHEMA", "MODIFY", "ALL PRIVILEGES"], priv)
    ])
    error_message = "Database privileges must be one of: USAGE, MONITOR, CREATE SCHEMA, MODIFY, ALL PRIVILEGES."
  }
}
