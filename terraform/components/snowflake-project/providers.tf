terraform {
  required_version = ">= 1.5.0"

  # Providers are pinned to a patch range, not a whole major: a new provider minor then falls
  # outside the constraint and Dependabot opens a pull request for it. The modules under
  # modules/snowflake/ keep the loose `~> 2.0`; this root pin is what decides the version.
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.21.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Snowflake providers: key-pair authentication as the Terraform service user
# created by terraform/modules/snowflake/init.sql. Values come from TF_VAR_SNOWFLAKE_* in .env.
#
# One connection per system role this component needs, so every object gets the owner
# Snowflake recommends (the role that creates an object owns it):
#   snowflake                databases, schemas, stages, warehouses  -> SYSADMIN
#   snowflake.securityadmin  roles and every grant (MANAGE GRANTS)   -> SECURITYADMIN
# Users (USERADMIN) are the snowflake-account component's.
# -----------------------------------------------------------------------------

provider "snowflake" {
  organization_name      = var.SNOWFLAKE_ORGANIZATION
  account_name           = var.SNOWFLAKE_ACCOUNT
  user                   = var.SNOWFLAKE_USER
  role                   = "SYSADMIN"
  warehouse              = var.SNOWFLAKE_WAREHOUSE
  authenticator          = "SNOWFLAKE_JWT"
  private_key            = file(pathexpand(var.SNOWFLAKE_PRIVATE_KEY_PATH))
  private_key_passphrase = var.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE
}

provider "snowflake" {
  alias                  = "securityadmin"
  organization_name      = var.SNOWFLAKE_ORGANIZATION
  account_name           = var.SNOWFLAKE_ACCOUNT
  user                   = var.SNOWFLAKE_USER
  role                   = "SECURITYADMIN"
  warehouse              = var.SNOWFLAKE_WAREHOUSE
  authenticator          = "SNOWFLAKE_JWT"
  private_key            = file(pathexpand(var.SNOWFLAKE_PRIVATE_KEY_PATH))
  private_key_passphrase = var.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE
}
