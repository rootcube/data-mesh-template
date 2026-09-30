# -----------------------------------------------------------------------------
# Input Variables
# -----------------------------------------------------------------------------

# Configuration Path, relative to this component directory (Atmos runs Terraform here)
variable "config_path" {
  description = "Path to the configuration directory containing YAML files"
  type        = string
  default     = "../../config"
}

# -----------------------------------------------------------------------------
# Provider Configuration
# -----------------------------------------------------------------------------

# Mapped to TF_VAR_SNOWFLAKE_ORGANIZATION environment variable
variable "SNOWFLAKE_ORGANIZATION" {
  description = "Snowflake organization name (the part before the dash in <organization>-<account>)"
  type        = string
}

# Mapped to TF_VAR_SNOWFLAKE_ACCOUNT environment variable
variable "SNOWFLAKE_ACCOUNT" {
  description = "Snowflake account name (the part after the dash in <organization>-<account>)"
  type        = string
}

# Mapped to TF_VAR_SNOWFLAKE_USER environment variable
variable "SNOWFLAKE_USER" {
  description = "Service user Terraform authenticates as (created by modules/snowflake/init.sql)"
  type        = string
  default     = "TERRAFORM_USER"
}

# Mapped to TF_VAR_SNOWFLAKE_WAREHOUSE environment variable
variable "SNOWFLAKE_WAREHOUSE" {
  description = "Warehouse for the provider's own queries (created by modules/snowflake/init.sql)"
  type        = string
  default     = "WH_PLATFORM_PROVISIONING"
}

# Mapped to TF_VAR_SNOWFLAKE_PRIVATE_KEY_PATH environment variable
variable "SNOWFLAKE_PRIVATE_KEY_PATH" {
  description = "Private key of the service user (generate with `just sf keygen terraform`)"
  type        = string
  default     = "~/.snowflake/keys/terraform.p8"
}

# Mapped to TF_VAR_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE environment variable
variable "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE" {
  description = "Passphrase of the private key, null when the key is not encrypted"
  type        = string
  default     = null
  sensitive   = true
}
