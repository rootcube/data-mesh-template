# =============================================================================
# Root Module Outputs
# =============================================================================
# Exposes key resource information for debugging and downstream integration.

# -----------------------------------------------------------------------------
# Database Outputs
# -----------------------------------------------------------------------------

output "databases" {
  description = "Map of created databases with their details"
  value = {
    for key, db in module.database : key => {
      name         = db.database_name
      id           = db.database_id
      project_code = db.project_code
      environment  = db.environment_code
    }
  }
}

output "database_names" {
  description = "List of all created database names"
  value       = [for db in module.database : db.database_name]
}

# -----------------------------------------------------------------------------
# Schema Outputs
# -----------------------------------------------------------------------------

output "schemas" {
  description = "Map of created schemas with their details"
  value = {
    for key, schema in module.schema : key => {
      name                 = schema.schema_name
      id                   = schema.schema_id
      database_name        = schema.database_name
      layer_code           = schema.layer_code
      fully_qualified_name = schema.fully_qualified_name
    }
  }
}

output "schema_names" {
  description = "List of all created schema names"
  value       = [for schema in module.schema : schema.schema_name]
}

# -----------------------------------------------------------------------------
# Warehouse Outputs
# -----------------------------------------------------------------------------

output "warehouses" {
  description = "Map of created warehouses with their details"
  value = {
    for key, wh in module.warehouse : key => {
      name        = wh.name
      id          = wh.id
      project     = wh.project
      environment = wh.environment
      profile     = wh.profile
      size        = wh.size
    }
  }
}

output "warehouse_names" {
  description = "List of all created warehouse names"
  value       = [for wh in module.warehouse : wh.name]
}

# -----------------------------------------------------------------------------
# Role Outputs
# -----------------------------------------------------------------------------

output "platform_roles" {
  description = "Map of created platform-level roles"
  value = {
    for key, role in module.platform_role : key => {
      name    = role.name
      id      = role.id
      purpose = role.purpose
    }
  }
}

output "project_roles" {
  description = "Map of created project-level roles"
  value = {
    for key, role in module.project_role : key => {
      name        = role.name
      id          = role.id
      project     = role.project
      environment = role.environment
      purpose     = role.purpose
    }
  }
}

output "role_names" {
  description = "List of all created role names (platform + project)"
  value = concat(
    [for role in module.platform_role : role.name],
    [for role in module.project_role : role.name]
  )
}

# -----------------------------------------------------------------------------
# Grant Summary Outputs
# -----------------------------------------------------------------------------

output "warehouse_grant_count" {
  description = "Number of warehouse grants created"
  value       = length(module.warehouse_grant)
}

output "database_grant_count" {
  description = "Number of database grants created"
  value       = length(module.database_grant)
}

output "schema_grant_count" {
  description = "Number of schema grants created"
  value       = length(module.schema_grant)
}

output "role_grant_count" {
  description = "Number of role-to-role grants created"
  value       = length(module.role_grant)
}

# -----------------------------------------------------------------------------
# Configuration Summary
# -----------------------------------------------------------------------------

output "config_summary" {
  description = "Summary of the loaded configuration"
  value = {
    project_count  = length(local.projects)
    role_count     = length(local.roles)
    layer_count    = length(local.layers)
    compute_count  = length(local.computes)
    enabled_roles  = [for k, r in local.roles : k if !try(r.disabled, false)]
    required_roles = [for k, r in local.roles : k if try(r.required, false)]
  }
}
