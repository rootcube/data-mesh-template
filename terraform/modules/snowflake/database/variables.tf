variable "project_code" {
  description = "The Project this database belongs to"
  type        = string

  validation {
    condition     = length(var.project_code) > 0 && can(regex("^[a-z][a-z0-9_]*$", var.project_code))
    error_message = "Project code must be lowercase alphanumeric with underscores, starting with a letter."
  }
}

variable "environment_code" {
  description = "The Environment (SBX, DEV, TST, ACC, PRD)"
  type        = string

  validation {
    condition     = contains(["sbx", "dev", "tst", "acc", "prd"], lower(var.environment_code))
    error_message = "Environment must be one of: sbx, dev, tst, acc, prd."
  }
}

variable "comment" {
  description = "Comment/description for the database"
  type        = string
  default     = ""
}

variable "data_retention_time_in_days" {
  description = "Number of days for which Snowflake retains historical data"
  type        = number
  default     = null # null: 30 days in prd, 7 in acc, 1 elsewhere (see main.tf)

  validation {
    condition     = var.data_retention_time_in_days == null || (var.data_retention_time_in_days >= 0 && var.data_retention_time_in_days <= 90)
    error_message = "Data retention must be between 0 and 90 days."
  }
}

variable "is_transient" {
  description = "Whether the database is transient (no Fail-safe)"
  type        = bool
  default     = false
}
