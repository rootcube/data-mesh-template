variable "project" {
  description = "The project this warehouse belongs to"
  type        = string

  validation {
    condition     = length(var.project) > 0
    error_message = "Project cannot be empty."
  }
}

variable "environment" {
  description = "The environment (SBX, DEV, TST, ACC, PRD)"
  type        = string

  validation {
    condition     = contains(["SBX", "DEV", "TST", "ACC", "PRD"], var.environment)
    error_message = "Environment must be one of: SBX, DEV, TST, ACC, PRD."
  }
}

variable "profile" {
  description = "The compute profile (e.g., LOADING, TRANSFORM, BI)"
  type        = string

  validation {
    condition     = length(var.profile) > 0
    error_message = "Profile cannot be empty."
  }
}

variable "size" {
  description = "The warehouse size (full Snowflake size name)"
  type        = string
  default     = "XSMALL"

  validation {
    condition     = contains(["XSMALL", "SMALL", "MEDIUM", "LARGE", "XLARGE", "XXLARGE", "XXXLARGE", "X4LARGE", "X5LARGE", "X6LARGE"], var.size)
    error_message = "Size must be a valid Snowflake warehouse size."
  }
}

variable "size_code" {
  description = "The warehouse size code (short code used in naming, e.g., 'xs', 'm', 'l')"
  type        = string
  default     = "xs"

  validation {
    condition     = contains(["xs", "s", "m", "l", "xl", "xxl", "xxxl", "x4l", "x5l", "x6l"], var.size_code)
    error_message = "Size code must be a valid short size code (xs, s, m, l, xl, xxl, xxxl, x4l, x5l, x6l)."
  }
}

variable "comment" {
  description = "Comment/description for the warehouse"
  type        = string
  default     = ""
}

variable "auto_suspend" {
  description = "Seconds of inactivity after which the warehouse is suspended"
  type        = number
  default     = 60

  validation {
    condition     = var.auto_suspend >= 0 && var.auto_suspend <= 3600
    error_message = "Auto suspend must be between 0 and 3600 seconds."
  }
}

variable "auto_resume" {
  description = "Whether the warehouse should automatically resume"
  type        = bool
  default     = true
}

variable "initially_suspended" {
  description = "Whether the warehouse should be created in suspended state"
  type        = bool
  default     = true
}

variable "min_cluster_count" {
  description = "Minimum number of clusters (for multi-cluster warehouses)"
  type        = number
  default     = 1

  validation {
    condition     = var.min_cluster_count >= 1 && var.min_cluster_count <= 10
    error_message = "Minimum cluster count must be between 1 and 10."
  }
}

variable "max_cluster_count" {
  description = "Maximum number of clusters (for multi-cluster warehouses)"
  type        = number
  default     = 1

  validation {
    condition     = var.max_cluster_count >= 1 && var.max_cluster_count <= 10
    error_message = "Maximum cluster count must be between 1 and 10."
  }
}

variable "scaling_policy" {
  description = "Scaling policy for multi-cluster warehouses"
  type        = string
  default     = "STANDARD"

  validation {
    condition     = contains(["STANDARD", "ECONOMY"], var.scaling_policy)
    error_message = "Scaling policy must be STANDARD or ECONOMY."
  }
}

variable "resource_monitor" {
  description = "Name of the resource monitor to assign to the warehouse"
  type        = string
  default     = null
}

variable "enable_query_acceleration" {
  description = "Whether to enable query acceleration"
  type        = bool
  default     = false
}

variable "query_acceleration_max_scale_factor" {
  description = "Maximum scale factor for query acceleration (0-100)"
  type        = number
  default     = 8
}
