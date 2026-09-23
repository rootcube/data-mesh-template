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
# Snowflake provider: key-pair authentication as the provisioning service user
# created by modules/snowflake/init.sql. Values come from TF_VAR_SNOWFLAKE_* in .env.
# -----------------------------------------------------------------------------

provider "snowflake" {
  organization_name      = var.SNOWFLAKE_ORGANIZATION
  account_name           = var.SNOWFLAKE_ACCOUNT
  user                   = var.SNOWFLAKE_USER
  role                   = var.SNOWFLAKE_PROVISIONING_ROLE
  warehouse              = var.SNOWFLAKE_WAREHOUSE
  authenticator          = "SNOWFLAKE_JWT"
  private_key            = file(pathexpand(var.SNOWFLAKE_PRIVATE_KEY_PATH))
  private_key_passphrase = var.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE
}
