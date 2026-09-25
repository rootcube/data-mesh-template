# -----------------------------------------------------------------------------
# Input Variables
# -----------------------------------------------------------------------------

# Configuration Path
variable "config_path" {
  description = "Path to the configuration directory containing YAML files"
  type        = string
  default     = "./config"
}

# -----------------------------------------------------------------------------
# Provider Configuration
# -----------------------------------------------------------------------------

# Mapped to TF_VAR_SNOWFLAKE_ORGANIZATION environment variable
variable "SNOWFLAKE_ORGANIZATION" {
  description = "Snowflake organization name (the part before the dash in <organization>-<account>)"
  type        = string
  sensitive   = true
}

# Mapped to TF_VAR_SNOWFLAKE_ACCOUNT environment variable
variable "SNOWFLAKE_ACCOUNT" {
  description = "Snowflake account name (the part after the dash in <organization>-<account>)"
  type        = string
  sensitive   = true
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

# -----------------------------------------------------------------------------
# Configuration from YAML Files
# -----------------------------------------------------------------------------
# All configuration is loaded from YAML files in the config directory.
# The YAML files are the single source of truth for platform configuration.
#
# Split Structure:
#   config/projects/**/*.yaml      - One file per project
#   config/roles/**/*.yaml         - One file per role
#   config/computes/**/*.yaml      - One file per compute profile
#   config/environments/**/*.yaml  - One file per environment
#   config/layers/**/*.yaml        - One file per layer
#   config/teams/**/*.yaml         - One file per team
#   config/organisations/**/*.yaml - One file per organisation
#   config/users/**/*.yaml         - One file per user (role assignments)

locals {
  # -------------------------------------------------------------------------
  # Load split configuration files
  # -------------------------------------------------------------------------

  # Load all project configurations from individual files
  project_files = fileset("${var.config_path}/projects", "**/*.yaml")
  projects_raw = {
    for f in local.project_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/projects/${f}"))
  }

  # Load all role configurations from individual files
  role_files = fileset("${var.config_path}/roles", "**/*.yaml")
  roles = {
    for f in local.role_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/roles/${f}"))
  }

  # Load all compute configurations from individual files
  compute_files = fileset("${var.config_path}/computes", "**/*.yaml")
  computes_raw = {
    for f in local.compute_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/computes/${f}"))
  }

  # Load all environment configurations from individual files
  environment_files = fileset("${var.config_path}/environments", "**/*.yaml")
  environments = {
    for f in local.environment_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/environments/${f}"))
  }

  # Load all layer configurations from individual files
  layer_files = fileset("${var.config_path}/layers", "**/*.yaml")
  layers = {
    for f in local.layer_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/layers/${f}"))
  }

  # Load all team configurations from individual files
  team_files = fileset("${var.config_path}/teams", "**/*.yaml")
  teams = {
    for f in local.team_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/teams/${f}"))
  }

  # Load all organisation configurations from individual files
  organisation_files = fileset("${var.config_path}/organisations", "**/*.yaml")
  organisations = {
    for f in local.organisation_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/organisations/${f}"))
  }

  # Load all user configurations from individual files (who may assume which project roles)
  user_files = fileset("${var.config_path}/users", "**/*.yaml")
  users = {
    for f in local.user_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/users/${f}"))
  }

  # -------------------------------------------------------------------------
  # Wildcard Resolution Lists
  # -------------------------------------------------------------------------

  # All enabled environment keys (for wildcard resolution)
  all_environment_keys = [
    for key, env in local.environments : key
    if !try(env.disabled, false)
  ]

  # All enabled layer keys (for wildcard resolution)
  all_layer_keys = [
    for key, layer in local.layers : key
    if !try(layer.disabled, false)
  ]

  # All enabled compute keys (for wildcard resolution)
  all_compute_keys = [
    for key, compute in local.computes_raw : key
    if !try(compute.disabled, false)
  ]

  # All enabled project-level role keys (for wildcard resolution)
  all_project_role_keys = [
    for key, role in local.roles : key
    if role.level == "project" && !try(role.disabled, false)
  ]

  # Required project-level role keys (always included for projects)
  required_role_keys = [
    for key, role in local.roles : key
    if role.level == "project" && !try(role.disabled, false) && try(role.required, false)
  ]

  # -------------------------------------------------------------------------
  # Code Lookup Maps (key -> code)
  # -------------------------------------------------------------------------
  # These maps allow looking up the short code for any concept by its key.
  # Used when generating resource names (which use codes, not keys).

  environment_codes = {
    for key, env in local.environments : key => env.code
  }

  layer_codes = {
    for key, layer in local.layers : key => layer.code
  }

  compute_codes = {
    for key, compute in local.computes_raw : key => compute.code
  }

  role_codes = {
    for key, role in local.roles : key => role.code
  }

  # -------------------------------------------------------------------------
  # Reverse Lookup Maps (code -> key)
  # -------------------------------------------------------------------------
  # These maps allow looking up the key for any concept by its code.
  # Used when role privileges reference concepts by code.

  environment_keys = {
    for key, env in local.environments : env.code => key
  }

  layer_keys = {
    for key, layer in local.layers : layer.code => key
  }

  compute_keys = {
    for key, compute in local.computes_raw : compute.code => key
    if compute.code != "" # Skip empty codes (default compute)
  }

  # Special handling for default compute which has empty code
  compute_keys_with_default = merge(
    local.compute_keys,
    { for key, compute in local.computes_raw : "" => key if compute.code == "" }
  )

  role_keys = {
    for key, role in local.roles : role.code => key
  }

  # -------------------------------------------------------------------------
  # Normalized Projects (with wildcards resolved)
  # -------------------------------------------------------------------------

  # Projects with wildcards expanded to actual values
  # The 'roles' property is authoritative - only listed roles (+ required) are created
  # All properties store KEYS (not codes) - use lookup maps to get codes when needed
  # Items that are disabled in their config files are filtered out, even if explicitly listed
  projects = {
    for code, project in local.projects_raw : code => merge(project, {
      # Resolve environments: "*" -> all enabled environment keys
      # Filter explicitly listed environments to only include enabled ones
      environments = [
        for env_key in(
          can(tostring(project.environments)) && project.environments == "*"
          ? local.all_environment_keys
          : try(tolist(project.environments), local.all_environment_keys)
        ) : env_key
        if contains(local.all_environment_keys, env_key)
      ]

      # Resolve layers: "*" -> all enabled layer keys
      # Filter explicitly listed layers to only include enabled ones
      layers = [
        for layer_key in(
          can(tostring(project.layers)) && project.layers == "*"
          ? local.all_layer_keys
          : try(tolist(project.layers), local.all_layer_keys)
        ) : layer_key
        if contains(local.all_layer_keys, layer_key)
      ]

      # Resolve computes: "*" -> all enabled compute keys
      # Filter explicitly listed computes to only include enabled ones
      computes = [
        for compute_key in(
          can(tostring(project.computes)) && project.computes == "*"
          ? local.all_compute_keys
          : try(tolist(project.computes), ["default"])
        ) : compute_key
        if contains(local.all_compute_keys, compute_key)
      ]

      # Resolve roles: "*" -> all enabled project role keys, otherwise use listed roles + required
      # The roles property is the AUTHORITATIVE source for which roles are created
      # Filter to only include enabled roles
      roles = [
        for role_key in distinct(concat(
          local.required_role_keys,
          can(tostring(project.roles)) && project.roles == "*"
          ? local.all_project_role_keys
          : try(tolist(project.roles), [])
        )) : role_key
        if contains(local.all_project_role_keys, role_key)
      ]
    })
  }

  # -------------------------------------------------------------------------
  # Compute configuration with size mapping
  # -------------------------------------------------------------------------

  # Warehouse size mapping
  compute_snowflake_warehouse_mapping = {
    xs   = "XSMALL"
    s    = "SMALL"
    m    = "MEDIUM"
    l    = "LARGE"
    xl   = "XLARGE"
    xxl  = "XXLARGE"
    xxxl = "XXXLARGE"
    x4l  = "X4LARGE"
    x5l  = "X5LARGE"
    x6l  = "X6LARGE"
  }

  # Merge compute configs with the size mapping reference
  computes = local.computes_raw
}
