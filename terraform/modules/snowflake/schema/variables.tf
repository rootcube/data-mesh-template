variable "database_name" {
  description = "The name of the database where the schema will be created"
  type        = string

  validation {
    condition     = length(var.database_name) > 0
    error_message = "Database name cannot be empty."
  }
}

variable "layer_code" {
  description = "The Layer code (e.g., src, stg, int, mrt, exp)"
  type        = string

  validation {
    condition     = length(var.layer_code) > 0 && can(regex("^[a-z]{3}$", var.layer_code))
    error_message = "Layer code must be exactly 3 lowercase letters."
  }
}

variable "comment" {
  description = "Comment/description for the schema"
  type        = string
  default     = ""
}

variable "is_transient" {
  description = "Whether the schema is transient (no Fail-safe)"
  type        = bool
  default     = false
}

variable "with_managed_access" {
  description = "Whether the schema uses managed access (centralized privilege management)"
  type        = bool
  default     = false
}

variable "data_retention_time_in_days" {
  description = "Number of days for which Snowflake retains historical data (inherits from database if null)"
  type        = number
  default     = 1

  validation {
    condition     = var.data_retention_time_in_days == null || (var.data_retention_time_in_days >= 0 && var.data_retention_time_in_days <= 90)
    error_message = "Data retention must be between 0 and 90 days."
  }
}
