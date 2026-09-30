# =============================================================================
# Component Outputs: the account-wide objects
# =============================================================================
# `just tf output snowflake-account -s account`; user_role_grants and initial_passwords
# (users.tf) sit next to their resources.

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

output "config_summary" {
  description = "Summary of the loaded configuration"
  value = {
    project_count  = length(local.projects)
    role_count     = length(local.roles)
    access_count   = length(module.config.accesses)
    layer_count    = length(module.config.layers)
    compute_count  = length(module.config.computes)
    enabled_roles  = [for k, r in local.roles : k if !try(r.disabled, false)]
    required_roles = [for k, r in local.roles : k if try(r.required, false)]
  }
}
