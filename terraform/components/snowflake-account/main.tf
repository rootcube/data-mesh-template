# -----------------------------------------------------------------------------
# Modern Data Mesh Platform - Snowflake Infrastructure: the account-wide objects
# -----------------------------------------------------------------------------
#
# This root module provisions what belongs to no single Project x Environment: the
# platform roles and the persons Terraform creates (users.tf). One Atmos stack
# (terraform/stacks/account.yaml), one Terraform state; the project stacks depend on it.
#
# Configuration is loaded from YAML files in the config directory by the config
# module (terraform/modules/config).
#
# -----------------------------------------------------------------------------

module "config" {
  source      = "../../modules/config"
  config_path = var.config_path
}

locals {
  # The configuration, under the names the locals below were written against
  projects          = module.config.projects
  roles             = module.config.roles
  users             = module.config.users
  environment_codes = module.config.environment_codes
  role_codes        = module.config.role_codes

  # Platform-level roles (created once, not scoped to project/environment)
  platform_roles = {
    for role_key, role in local.roles :
    role_key => role
    if role.level == "platform" && !try(role.disabled, false)
  }
}

# -----------------------------------------------------------------------------
# Platform Roles (Global)
# -----------------------------------------------------------------------------

module "platform_role" {
  source    = "../../modules/snowflake/role"
  for_each  = local.platform_roles
  providers = { snowflake = snowflake.securityadmin }

  purpose = upper(each.value.code)
  comment = each.value.desc

  # Custom roles roll up to SYSADMIN, so it can manage whatever they create.
  granted_to_roles = ["SYSADMIN"]
}
