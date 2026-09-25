terraform {
  required_version = ">= 1.5.0"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# -----------------------------------------------------------------------------
# Snowflake providers: key-pair authentication as the Terraform service user
# created by modules/snowflake/init.sql. Values come from TF_VAR_SNOWFLAKE_* in .env.
#
# One connection per system role, so every object gets the owner Snowflake recommends
# (the role that creates an object owns it):
#   snowflake                databases, schemas, stages, warehouses  -> SYSADMIN
#   snowflake.securityadmin  roles and every grant (MANAGE GRANTS)   -> SECURITYADMIN
#   snowflake.useradmin      users                                   -> USERADMIN
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

provider "snowflake" {
  alias                  = "useradmin"
  organization_name      = var.SNOWFLAKE_ORGANIZATION
  account_name           = var.SNOWFLAKE_ACCOUNT
  user                   = var.SNOWFLAKE_USER
  role                   = "USERADMIN"
  warehouse              = var.SNOWFLAKE_WAREHOUSE
  authenticator          = "SNOWFLAKE_JWT"
  private_key            = file(pathexpand(var.SNOWFLAKE_PRIVATE_KEY_PATH))
  private_key_passphrase = var.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE
}
