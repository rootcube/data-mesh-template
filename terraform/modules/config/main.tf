# -----------------------------------------------------------------------------
# Config Module: the platform's YAML configuration (terraform/config), loaded and normalized
# -----------------------------------------------------------------------------
# No resources: both components (terraform/components/snowflake-account and
# snowflake-project) read the same YAML through this module, so the wildcard
# resolution, code maps and defaults below exist once.

variable "config_path" {
  description = "Path to the configuration directory containing YAML files"
  type        = string
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
#   config/accesses/**/*.yaml      - One file per access tier (view, read, edit, full)
#   config/users/**/*.yaml         - One file per user (role assignments)
#
# config/teams and config/organisations name no Snowflake object; only
# config/_validation/validate_configs.py reads them (cross-references).

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

  # Load all user configurations from individual files (who may assume which project roles)
  # Keyed by file name alone, so a user file can live in a sub-folder (users/local/, git-ignored)
  user_files = fileset("${var.config_path}/users", "**/*.yaml")
  users = {
    for f in local.user_files :
    trimsuffix(basename(f), ".yaml") => yamldecode(file("${var.config_path}/users/${f}"))
  }

  # Load all access tier configurations (view, read, edit, full: the privilege tiers on a layer)
  access_files = fileset("${var.config_path}/accesses", "**/*.yaml")
  accesses = {
    for f in local.access_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${var.config_path}/accesses/${f}"))
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

  access_codes = {
    for key, access in local.accesses : key => access.code
  }

  # -------------------------------------------------------------------------
  # Layer access privileges (layer key -> access key -> privileges)
  # -------------------------------------------------------------------------
  # What an access tier grants on a layer: the tier's own privileges (config/accesses) plus the
  # layer's extras for that tier (`privileges` in config/layers, e.g. stages in the source layer).
  # Used for the layer access roles and the personal schemas (components/snowflake-project).

  layer_access_privileges = {
    for layer_key, layer in local.layers : layer_key => {
      for access_key, access in local.accesses : access_key => distinct(concat(
        access.privileges,
        try(layer.privileges[access_key], [])
      ))
    }
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

  # Defaults of the optional compute attributes, the same ones compute.schema.json documents.
  # The project component reads these keys unguarded, so a YAML that leaves them out must still have them.
  # `sizes` has no sensible default and is required in the schema.
  compute_defaults = {
    desc              = ""
    disabled          = false
    required          = false
    auto_suspend      = 60
    auto_resume       = true
    min_cluster_count = 1
    max_cluster_count = 1
  }

  computes = {
    for key, compute in local.computes_raw : key => merge(local.compute_defaults, compute)
  }
}

# -----------------------------------------------------------------------------
# Outputs: the normalized configuration, under the names the components use as locals
# -----------------------------------------------------------------------------

output "projects" {
  description = "Projects keyed by file name, wildcards resolved and disabled entries filtered out"
  value       = local.projects
}

output "roles" {
  description = "Roles keyed by file name (config/roles, sub-folders included)"
  value       = local.roles
}

output "computes" {
  description = "Compute profiles keyed by file name, with the defaults of the optional attributes"
  value       = local.computes
}

output "environments" {
  description = "Environments keyed by file name"
  value       = local.environments
}

output "layers" {
  description = "Layers keyed by file name"
  value       = local.layers
}

output "accesses" {
  description = "Access tiers keyed by file name (view, read, edit, full)"
  value       = local.accesses
}

output "users" {
  description = "User files keyed by file name alone (config/users, users/local included)"
  value       = local.users
}

output "environment_codes" {
  description = "Environment key -> code (development -> dev)"
  value       = local.environment_codes
}

output "layer_codes" {
  description = "Layer key -> code"
  value       = local.layer_codes
}

output "compute_codes" {
  description = "Compute key -> code"
  value       = local.compute_codes
}

output "role_codes" {
  description = "Role key -> code"
  value       = local.role_codes
}

output "layer_access_privileges" {
  description = "Layer key -> access key -> privileges (the tier's own plus the layer's extras)"
  value       = local.layer_access_privileges
}

output "compute_snowflake_warehouse_mapping" {
  description = "Warehouse size code -> Snowflake warehouse size"
  value       = local.compute_snowflake_warehouse_mapping
}
