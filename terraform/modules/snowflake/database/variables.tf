variable "project_code" {
  description = "The Project this database belongs to"
  type        = string

  validation {
    condition     = length(var.project_code) > 0 && can(regex("^[a-z][a-z0-9_]*$", var.project_code))
    error_message = "Project code must be lowercase alphanumeric with underscores, starting with a letter."
  }
}

variable "environment_code" {
  description = "The Environment code (SBX, DEV, TST, ACC, PRD, or any other in config/environments)"
  type        = string

  validation {
    # Same shape as `code` in environment.schema.json, so a new environment needs no module change.
    condition     = can(regex("^[a-z]{3}$", lower(var.environment_code)))
    error_message = "Environment code must be three letters (see config/environments)."
  }
}

variable "comment" {
  description = "Comment/description for the database"
  type        = string
  default     = ""
}

variable "data_retention_time_in_days" {
  description = "Number of days for which Snowflake retains historical data (Time Travel)"
  type        = number
  # 1 is the Standard Edition maximum; raise it per environment with `data_retention_days` in
  # config/environments. An environment without that key passes null, hence nullable = false.
  default  = 1
  nullable = false

  validation {
    condition     = var.data_retention_time_in_days >= 0 && var.data_retention_time_in_days <= 90
    error_message = "Data retention must be between 0 and 90 days."
  }
}

variable "is_transient" {
  description = "Whether the database is transient (no Fail-safe)"
  type        = bool
  default     = false
}
