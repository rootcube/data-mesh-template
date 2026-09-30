# =============================================================================
# Component Outputs: one Project x Environment
# =============================================================================
# `just tf output snowflake-project -s <project>-<env>`; stage_names (stages.tf) and
# personal_schemas (personal.tf) sit next to their resources.

# The stack this state belongs to. The precondition stops a plan whose stack names a project or
# environment code that config/ does not have, which would otherwise plan to remove everything.
output "stack" {
  description = "Project and environment code of this stack"
  value       = "${var.project}-${var.environment}"

  precondition {
    condition     = contains(keys(local.projects), var.project) && length(try(local.projects[var.project].environments, [])) == 1
    error_message = "Stack ${var.project}-${var.environment}: config/projects/${var.project}.yaml does not exist, or does not list an enabled environment with code ${var.environment} (config/environments)."
  }
}

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

output "access_roles" {
  description = "Map of created layer access roles (AR_<PROJECT>_<ENV>__<LAYER>__<ACCESS>), one per layer and access tier in every project database"
  value = {
    for key, role in module.access_role : key => {
      name        = role.name
      id          = role.id
      project     = role.project
      environment = role.environment
      layer       = local.access_role_map[key].layer_key
      access      = local.access_role_map[key].access_key
    }
  }
}

output "role_names" {
  description = "List of all created role names (project + access)"
  value = concat(
    [for role in module.project_role : role.name],
    [for role in module.access_role : role.name]
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
  description = "Number of layer schema grant sets created (one per access role)"
  value       = length(module.access_role_grant)
}

output "role_grant_count" {
  description = "Number of role-to-role grants created (project role inheritance)"
  value       = length(module.role_grant)
}

output "role_access_grant_count" {
  description = "Number of access role grants to project roles created (role x layer)"
  value       = length(module.role_access_grant)
}
