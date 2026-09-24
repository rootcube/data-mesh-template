variable "project" {
  description = "The project this role belongs to (leave empty for platform-level roles)"
  type        = string
  default     = ""
}

variable "environment" {
  description = "The environment (SBX, DEV, TST, ACC, PRD) - required for project roles"
  type        = string
  default     = ""

  validation {
    condition     = var.environment == "" || contains(["SBX", "DEV", "TST", "ACC", "PRD"], var.environment)
    error_message = "Environment must be empty or one of: SBX, DEV, TST, ACC, PRD."
  }
}

variable "purpose" {
  description = "The purpose/type of the role (e.g., READER, WRITER, ADMIN, DEVELOPER)"
  type        = string

  validation {
    condition     = can(regex("^[A-Z][A-Z0-9_]*$", var.purpose))
    error_message = "Purpose must be uppercase alphanumeric with underscores, starting with a letter."
  }
}

variable "comment" {
  description = "Comment/description for the role"
  type        = string
  default     = ""
}

variable "granted_roles" {
  description = "List of roles to grant to this role (role hierarchy)"
  type        = list(string)
  default     = []
}

variable "granted_to_roles" {
  description = "List of roles this role should be granted to"
  type        = list(string)
  default     = []
}

variable "granted_to_users" {
  description = "List of users this role should be granted to"
  type        = list(string)
  default     = []
}
