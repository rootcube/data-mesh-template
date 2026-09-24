# =============================================================================
# Schema Grant Module - Variables
# =============================================================================

variable "database_name" {
  type        = string
  description = "Name of the database containing the schema"

  validation {
    condition     = length(var.database_name) > 0
    error_message = "Database name cannot be empty."
  }
}

variable "schema_name" {
  type        = string
  description = "Name of the schema to grant privileges on"

  validation {
    condition     = length(var.schema_name) > 0
    error_message = "Schema name cannot be empty."
  }
}

variable "role_name" {
  type        = string
  description = "Name of the role to grant privileges to"

  validation {
    condition     = length(var.role_name) > 0
    error_message = "Role name cannot be empty."
  }
}

variable "privileges" {
  type        = list(string)
  description = "List of privileges to grant. Schema privileges (e.g., USAGE, CREATE TABLE) or object privileges (e.g., SELECT ON TABLES)"

  validation {
    condition = alltrue([
      for p in var.privileges : can(regex("^(USAGE|MODIFY|MONITOR|CREATE [A-Z ]+|ADD SEARCH OPTIMIZATION|[A-Z]+ ON [A-Z ]+)$", p))
    ])
    error_message = "Invalid privilege format. Must be a schema privilege (USAGE, MODIFY, MONITOR, CREATE X, ADD SEARCH OPTIMIZATION) or object privilege (X ON Y)."
  }

  validation {
    condition     = length(var.privileges) > 0
    error_message = "At least one privilege must be specified."
  }
}
