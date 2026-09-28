# -----------------------------------------------------------------------------
# Modern Data Mesh Platform - Snowflake Infrastructure
# -----------------------------------------------------------------------------
#
# This root module orchestrates the provisioning of Snowflake resources
# based on the platform's conceptual model:
#
#   Organisation -> Team -> Project -> Environment -> { Layers, Roles, Compute }
#
# Configuration is loaded from YAML files in the config directory.
# See variables.tf for the locals that parse these YAML files.
#
# -----------------------------------------------------------------------------

locals {
  # Build a flattened list of all project-environment combinations
  # Keys are used for Terraform resource IDs, codes are used for generated names
  # Resource type is included in the key for clarity (e.g., fundana_production_database)
  project_environments = flatten([
    for project_key, project in local.projects : [
      for environment_key in project.environments : {
        key              = "${project_key}_${environment_key}_database"
        project_key      = project_key
        environment_key  = environment_key
        environment_code = local.environment_codes[environment_key]
        project_config   = project
      }
    ]
  ])

  # Convert to map for for_each
  project_environment_map = {
    for pe in local.project_environments : pe.key => pe
  }

  # Build a flattened list of all project-environment-layer combinations
  # Each project defines its own layers, creating schemas per layer per database
  project_environment_layers = flatten([
    for project_key, project in local.projects : [
      for environment_key in project.environments : [
        for layer_key in project.layers : {
          key              = "${project_key}_${environment_key}_schema_${layer_key}"
          project_key      = project_key
          environment_key  = environment_key
          environment_code = local.environment_codes[environment_key]
          layer_key        = layer_key
          layer_code       = local.layer_codes[layer_key]
          database_name    = upper("DB_${project_key}_${local.environment_codes[environment_key]}")
        }
      ]
    ]
  ])

  # Convert to map for for_each
  project_environment_layer_map = {
    for pel in local.project_environment_layers : pel.key => pel
  }

  # --------------------------------------------------------------------------
  # Roles
  # --------------------------------------------------------------------------

  # Platform-level roles (created once, not scoped to project/environment)
  platform_roles = {
    for role_key, role in local.roles :
    role_key => role
    if role.level == "platform" && !try(role.disabled, false)
  }

  # Project-level roles (created per Project x Environment)
  # The project.roles list is the AUTHORITATIVE source for which roles are created
  # Only roles explicitly listed in project.roles (plus required roles) are created
  project_environment_roles = flatten([
    for project_key, project in local.projects : [
      for environment_key in project.environments : [
        for role_key in project.roles : {
          key              = "${project_key}_${environment_key}_role_${role_key}"
          project_key      = project_key
          environment_key  = environment_key
          environment_code = local.environment_codes[environment_key]
          role_key         = role_key
          role_code        = local.role_codes[role_key]
          role_config      = local.roles[role_key]
        }
        if contains(keys(local.roles), role_key) &&
        local.roles[role_key].level == "project" &&
        !try(local.roles[role_key].disabled, false)
      ]
    ]
  ])

  # Convert to map for for_each
  project_environment_role_map = {
    for per in local.project_environment_roles : per.key => per
  }

  # --------------------------------------------------------------------------
  # Warehouses (Computes)
  # --------------------------------------------------------------------------

  # Size code to Snowflake warehouse size mapping
  warehouse_size_mapping = local.compute_snowflake_warehouse_mapping

  # Project-level warehouses (created per Project x Environment x Compute x Size)
  project_environment_warehouses = flatten([
    for project_key, project in local.projects : [
      for environment_key in project.environments : [
        for compute_key in project.computes : [
          for size_code in local.computes[compute_key].sizes : {
            key              = "${project_key}_${environment_key}_warehouse_${compute_key}_${size_code}"
            project_key      = project_key
            environment_key  = environment_key
            environment_code = local.environment_codes[environment_key]
            compute_key      = compute_key
            compute_code     = local.compute_codes[compute_key]
            compute_config   = local.computes[compute_key]
            size_code        = size_code
            size             = upper(local.warehouse_size_mapping[size_code])
          }
        ]
        if local.computes[compute_key].disabled != true
      ]
    ]
  ])

  # Convert to map for for_each
  project_environment_warehouse_map = {
    for pew in local.project_environment_warehouses : pew.key => pew
  }

  # --------------------------------------------------------------------------
  # Warehouse Grants (Role x Compute with specific privileges)
  # --------------------------------------------------------------------------

  # Build a flat list of warehouse grants: one entry per role x compute x size combination
  # (every size of a compute is its own warehouse)
  # Privileges are resolved using environment-specific overrides or defaults
  # Only roles in project.roles are considered (authoritative source)
  # Note: Role privileges use codes (e.g., 'default'), project.computes uses keys (e.g., 'default')
  warehouse_grants = flatten([
    for project_key, project in local.projects : [
      for environment_key in project.environments : [
        for role_key in project.roles : [
          # compute_code here is actually the key used in role.privileges.computes (which happens to be the key, not the code)
          for compute_key, env_privileges in try(local.roles[role_key].privileges.computes, {}) : [
            for size_code in local.computes[compute_key].sizes : {
              # The first size keeps the key it had before every size was granted, so applied grants are not
              # re-created (a REVOKE racing the new GRANT); only the extra sizes carry the size in the key.
              key              = "${project_key}_${environment_key}_warehouse_grant_${role_key}_${compute_key}${size_code == local.computes[compute_key].sizes[0] ? "" : "_${size_code}"}"
              project_key      = project_key
              environment_key  = environment_key
              environment_code = local.environment_codes[environment_key]
              role_key         = role_key
              role_code        = local.role_codes[role_key]
              compute_key      = compute_key
              compute_code     = local.compute_codes[compute_key]
              size_code        = size_code

              # Role name follows the pattern: RL_<PROJECT>_<ENV>__<PURPOSE>
              role_name = upper("RL_${project_key}_${local.environment_codes[environment_key]}__${local.role_codes[role_key]}")

              # Build warehouse name using short size codes (e.g., 'xs', 'm', 'l')
              warehouse_name = upper(
                local.compute_codes[compute_key] == "" ?
                "WH_${project_key}_${local.environment_codes[environment_key]}" :
                "WH_${project_key}_${local.environment_codes[environment_key]}__${local.compute_codes[compute_key]}_${size_code}"
              )

              # Try environment-specific privileges first, fall back to all
              # Note: Role privilege definitions still use environment codes (dev, prd, etc.)
              privileges = try(
                env_privileges[local.environment_codes[environment_key]],
                try(env_privileges["all"], [])
              )
            }
          ]
          if contains(keys(local.roles), role_key) &&
          contains(keys(local.computes), compute_key) &&
          contains(project.computes, compute_key) &&
          !try(local.computes[compute_key].disabled, false) &&
          length(try(env_privileges[local.environment_codes[environment_key]], try(env_privileges["all"], []))) > 0
        ]
        if contains(keys(local.roles), role_key) &&
        local.roles[role_key].level == "project" &&
        !try(local.roles[role_key].disabled, false)
      ]
    ]
  ])

  # Convert to map for for_each
  warehouse_grant_map = {
    for wg in local.warehouse_grants : wg.key => wg
  }

  # --------------------------------------------------------------------------
  # Database Grants (Role x Database with USAGE privilege)
  # --------------------------------------------------------------------------

  # Each project-level role needs USAGE on its project's database
  # This is a prerequisite for any schema-level access
  # Only roles in project.roles are considered (authoritative source)
  database_grants = flatten([
    for project_key, project in local.projects : [
      for environment_key in project.environments : [
        for role_key in project.roles : {
          key              = "${project_key}_${environment_key}_database_grant_${role_key}"
          project_key      = project_key
          environment_key  = environment_key
          environment_code = local.environment_codes[environment_key]
          role_key         = role_key
          role_code        = local.role_codes[role_key]

          # Role name follows the pattern: RL_<PROJECT>_<ENV>__<PURPOSE>
          role_name = upper("RL_${project_key}_${local.environment_codes[environment_key]}__${local.role_codes[role_key]}")

          # Database name follows the pattern: DB_<PROJECT>_<ENV>
          database_name = upper("DB_${project_key}_${local.environment_codes[environment_key]}")

          # USAGE by default; a role may add e.g. MONITOR per environment under
          # privileges.database. Personal schemas come from personal.tf, not CREATE SCHEMA.
          privileges = distinct(concat(["USAGE"], try(
            local.roles[role_key].privileges.database[local.environment_codes[environment_key]],
            try(local.roles[role_key].privileges.database["all"], [])
          )))
        }
        if contains(keys(local.roles), role_key) &&
        local.roles[role_key].level == "project" &&
        !try(local.roles[role_key].disabled, false) &&
        try(local.roles[role_key].privileges.layers, null) != null
      ]
    ]
  ])

  # Convert to map for for_each
  database_grant_map = {
    for dg in local.database_grants : dg.key => dg
  }

  # --------------------------------------------------------------------------
  # Role Grants (Role inheritance - role to role grants)
  # --------------------------------------------------------------------------

  # Build a flat list of role grants: one entry per role x parent_role combination
  # The roles privilege is a map of parent_role_key -> list of environments (or [all])
  # Only roles in project.roles are considered (authoritative source)
  role_grants = flatten([
    for project_key, project in local.projects : [
      for environment_key in project.environments : [
        for role_key in project.roles : [
          for parent_role_key, environments in try(local.roles[role_key].privileges.roles, {}) : {
            key              = "${project_key}_${environment_key}_role_grant_${role_key}_${parent_role_key}"
            project_key      = project_key
            environment_key  = environment_key
            environment_code = local.environment_codes[environment_key]
            role_key         = role_key
            role_code        = local.role_codes[role_key]
            parent_role_key  = parent_role_key
            parent_role_code = local.role_codes[parent_role_key]

            # Child role name (the role that will inherit)
            role_name = upper("RL_${project_key}_${local.environment_codes[environment_key]}__${local.role_codes[role_key]}")

            # Parent role name (the role to inherit from)
            parent_role_name = upper("RL_${project_key}_${local.environment_codes[environment_key]}__${local.role_codes[parent_role_key]}")
          }
          if contains(keys(local.roles), parent_role_key) &&
          contains(project.roles, parent_role_key) &&
          local.roles[parent_role_key].level == "project" &&
          !try(local.roles[parent_role_key].disabled, false) &&
          (contains(environments, "all") || contains(environments, local.environment_codes[environment_key]))
        ]
        if contains(keys(local.roles), role_key) &&
        local.roles[role_key].level == "project" &&
        !try(local.roles[role_key].disabled, false)
      ]
    ]
  ])

  # Convert to map for for_each
  role_grant_map = {
    for rg in local.role_grants : rg.key => rg
  }

  # --------------------------------------------------------------------------
  # Access Roles (Project x Environment x Layer x Access tier)
  # --------------------------------------------------------------------------

  # One access role per layer and access tier (config/accesses: view, read, edit, full) in every
  # project database: AR_<PROJECT>_<ENV>__<LAYER>__<ACCESS>, with the tier's privileges (plus the
  # layer's extras, variables.tf) on the layer schema. All four exist for every layer, whether a
  # project role uses them or not, so every layer has the same four doors.
  project_environment_layer_accesses = flatten([
    for pel in local.project_environment_layers : [
      for access_key, access in local.accesses : {
        key              = "${pel.project_key}_${pel.environment_key}_access_role_${pel.layer_key}_${access_key}"
        project_key      = pel.project_key
        environment_key  = pel.environment_key
        environment_code = pel.environment_code
        layer_key        = pel.layer_key
        layer_code       = pel.layer_code
        access_key       = access_key
        access_code      = access.code

        # Database, and the key of the layer schema in module.schema (which names it)
        database_name = pel.database_name
        schema_key    = pel.key

        privileges = local.layer_access_privileges[pel.layer_key][access_key]
      }
    ]
  ])

  # Convert to map for for_each
  access_role_map = {
    for pela in local.project_environment_layer_accesses : pela.key => pela
  }

  # --------------------------------------------------------------------------
  # Layer Access (Role x Layer -> access tier, per Environment)
  # --------------------------------------------------------------------------

  # One entry per project role x layer: the access tier the role holds on that layer in that
  # environment, from privileges.layers (the environment code first, then 'all'). The role does
  # not get the privileges itself: it inherits the layer's access role (above). Only roles and
  # layers the project lists count; a layer without a tier for the role in that environment is
  # skipped.
  role_layer_accesses = flatten([
    for project_key, project in local.projects : [
      for environment_key in project.environments : [
        for role_key in project.roles : [
          # layer_key is the key used in role.privileges.layers (e.g., 'mart')
          for layer_key, access_by_environment in try(local.roles[role_key].privileges.layers, {}) : {
            key              = "${project_key}_${environment_key}_layer_access_${role_key}_${layer_key}"
            project_key      = project_key
            environment_key  = environment_key
            environment_code = local.environment_codes[environment_key]
            role_key         = role_key
            layer_key        = layer_key
            access_key       = try(access_by_environment[local.environment_codes[environment_key]], access_by_environment["all"])

            # Role name follows the pattern: RL_<PROJECT>_<ENV>__<PURPOSE>
            role_name = upper("RL_${project_key}_${local.environment_codes[environment_key]}__${local.role_codes[role_key]}")

            # Key of the access role this role inherits for the layer (access_role_map above)
            access_role_key = "${project_key}_${environment_key}_access_role_${layer_key}_${try(access_by_environment[local.environment_codes[environment_key]], access_by_environment["all"])}"
          }
          if contains(keys(local.layer_codes), layer_key) &&
          contains(project.layers, layer_key) &&
          (contains(keys(access_by_environment), local.environment_codes[environment_key]) || contains(keys(access_by_environment), "all"))
        ]
        if contains(keys(local.roles), role_key) &&
        local.roles[role_key].level == "project" &&
        !try(local.roles[role_key].disabled, false)
      ]
    ]
  ])

  # Convert to map for for_each
  role_access_grant_map = {
    for rla in local.role_layer_accesses : rla.key => rla
  }
}

# -----------------------------------------------------------------------------
# Databases (Project x Environment)
# -----------------------------------------------------------------------------

module "database" {
  source   = "./modules/snowflake/database"
  for_each = local.project_environment_map

  project_code     = each.value.project_key
  environment_code = each.value.environment_code

  # Time Travel retention of the environment, the module's default when the YAML leaves it out
  data_retention_time_in_days = try(local.environments[each.value.environment_key].data_retention_days, null)
}

# -----------------------------------------------------------------------------
# Schemas (Project x Environment x Layer)
# -----------------------------------------------------------------------------

module "schema" {
  source   = "./modules/snowflake/schema"
  for_each = local.project_environment_layer_map

  database_name = each.value.database_name
  layer_code    = each.value.layer_code

  # Ensure database exists before creating schema
  depends_on = [module.database]
}

# -----------------------------------------------------------------------------
# Platform Roles (Global)
# -----------------------------------------------------------------------------

module "platform_role" {
  source    = "./modules/snowflake/role"
  for_each  = local.platform_roles
  providers = { snowflake = snowflake.securityadmin }

  purpose = upper(each.value.code)
  comment = each.value.desc

  # Custom roles roll up to SYSADMIN, so it can manage whatever they create.
  granted_to_roles = ["SYSADMIN"]
}

# -----------------------------------------------------------------------------
# Project Roles (Project x Environment)
# -----------------------------------------------------------------------------

module "project_role" {
  source    = "./modules/snowflake/role"
  for_each  = local.project_environment_role_map
  providers = { snowflake = snowflake.securityadmin }

  project     = upper(each.value.project_key)
  environment = upper(each.value.environment_code)
  purpose     = upper(each.value.role_code)
  comment     = each.value.role_config.desc

  # Custom roles roll up to SYSADMIN, so it can manage whatever they create.
  granted_to_roles = ["SYSADMIN"]
}

# -----------------------------------------------------------------------------
# Warehouses (Project x Environment x Compute x Size)
# -----------------------------------------------------------------------------

module "warehouse" {
  source   = "./modules/snowflake/warehouse"
  for_each = local.project_environment_warehouse_map

  project     = upper(each.value.project_key)
  environment = upper(each.value.environment_code)
  profile     = upper(each.value.compute_code != "" ? each.value.compute_code : "DEFAULT")
  size        = each.value.size
  size_code   = each.value.size_code
  comment     = each.value.compute_config.desc

  auto_suspend      = each.value.compute_config.auto_suspend
  auto_resume       = each.value.compute_config.auto_resume
  min_cluster_count = each.value.compute_config.min_cluster_count
  max_cluster_count = each.value.compute_config.max_cluster_count
}

# -----------------------------------------------------------------------------
# Warehouse Grants (Warehouse privileges per Role per Environment)
# -----------------------------------------------------------------------------

module "warehouse_grant" {
  source    = "./modules/snowflake/warehouse_grant"
  for_each  = local.warehouse_grant_map
  providers = { snowflake = snowflake.securityadmin }

  role_name      = each.value.role_name
  warehouse_name = each.value.warehouse_name
  privileges     = each.value.privileges

  # Ensure roles and warehouses exist before creating grants
  depends_on = [
    module.project_role,
    module.warehouse
  ]
}

# -----------------------------------------------------------------------------
# Database Grants (Database privileges per Role per Environment)
# -----------------------------------------------------------------------------

module "database_grant" {
  source    = "./modules/snowflake/database_grant"
  for_each  = local.database_grant_map
  providers = { snowflake = snowflake.securityadmin }

  role_name     = each.value.role_name
  database_name = each.value.database_name
  privileges    = each.value.privileges

  # Ensure roles and databases exist before creating grants
  depends_on = [
    module.project_role,
    module.database
  ]
}

# -----------------------------------------------------------------------------
# Role Grants (Role inheritance per Role per Environment)
# -----------------------------------------------------------------------------

module "role_grant" {
  source    = "./modules/snowflake/role_grant"
  for_each  = local.role_grant_map
  providers = { snowflake = snowflake.securityadmin }

  role_name        = each.value.role_name
  parent_role_name = each.value.parent_role_name

  # Ensure both roles exist before creating grants
  depends_on = [
    module.project_role
  ]
}

# -----------------------------------------------------------------------------
# Access Roles (Layer x Access tier): hold the privileges on a layer schema
# -----------------------------------------------------------------------------

module "access_role" {
  source    = "./modules/snowflake/role"
  for_each  = local.access_role_map
  providers = { snowflake = snowflake.securityadmin }

  prefix      = "AR"
  project     = upper(each.value.project_key)
  environment = upper(each.value.environment_code)
  purpose     = upper("${each.value.layer_code}__${each.value.access_code}")
  comment     = "Access role: ${each.value.access_key} on layer ${each.value.layer_key} (${each.value.database_name}.${module.schema[each.value.schema_key].schema_name})"

  # Not granted to SYSADMIN directly: access roles reach it through the project roles that hold them.
}

# -----------------------------------------------------------------------------
# Access Role Grants (Schema and object privileges per Access role per Layer)
# -----------------------------------------------------------------------------

module "access_role_grant" {
  source    = "./modules/snowflake/schema_grant"
  for_each  = local.access_role_map
  providers = { snowflake = snowflake.securityadmin }

  role_name     = module.access_role[each.key].name
  database_name = each.value.database_name
  schema_name   = module.schema[each.value.schema_key].schema_name
  privileges    = each.value.privileges

  # Ensure databases and schemas exist before creating grants
  depends_on = [
    module.database,
    module.schema
  ]
}

# -----------------------------------------------------------------------------
# Layer Access Grants (Access role -> Project role, per Layer per Environment)
# -----------------------------------------------------------------------------

module "role_access_grant" {
  source    = "./modules/snowflake/role_grant"
  for_each  = local.role_access_grant_map
  providers = { snowflake = snowflake.securityadmin }

  # The project role inherits the access role of the layer
  role_name        = each.value.role_name
  parent_role_name = module.access_role[each.value.access_role_key].name

  # Ensure the project roles exist before granting (the access roles come through the reference above)
  depends_on = [
    module.project_role
  ]
}
