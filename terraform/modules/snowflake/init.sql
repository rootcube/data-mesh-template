-- =============================================================================
-- Snowflake Platform Provisioning Setup for Terraform
-- =============================================================================
-- Run this script as ACCOUNTADMIN (`just sf bootstrap` does). Every statement is
-- idempotent, so it is safe to run again on an account that was set up before.
--
-- Terraform provisions through Snowflake's system roles, so every object ends up
-- with the owner Snowflake recommends (see the providers.tf of the components under terraform/components):
--   SYSADMIN       databases, schemas, stages, warehouses
--   SECURITYADMIN  roles and all grants (MANAGE GRANTS)
--   USERADMIN      users
--
-- Account parameters (UTC, ISO weeks and formats, security defaults) live in
-- account_settings.sql, which the bootstrap asks about separately.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- -----------------------------------------------------------------------------
-- 1. Create Service User (key pair authentication only)
-- -----------------------------------------------------------------------------
CREATE USER IF NOT EXISTS TERRAFORM_USER
;

ALTER USER IF EXISTS TERRAFORM_USER SET
  COMMENT = 'Service user for Provisioning with Terraform'
  TYPE = SERVICE
  --RSA_PUBLIC_KEY = '<INSERT_YOUR_RSA_PUBLIC_KEY_HERE>' --> https://docs.snowflake.com/en/user-guide/key-pair-auth#configuring-key-pair-authentication
;

-- Force disable password authentication (allowed key pair only)
ALTER USER IF EXISTS TERRAFORM_USER UNSET PASSWORD
;


-- -----------------------------------------------------------------------------
-- 2. Create Warehouses (owned by SYSADMIN)
-- -----------------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS WH_PLATFORM_PROVISIONING
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = True
  INITIALLY_SUSPENDED = True
  COMMENT = 'Warehouse for Terraform platform provisioning'
;

ALTER WAREHOUSE IF EXISTS WH_PLATFORM_PROVISIONING SET
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = True
  COMMENT = 'Warehouse for Terraform platform provisioning'
;

GRANT OWNERSHIP ON WAREHOUSE WH_PLATFORM_PROVISIONING TO ROLE SYSADMIN COPY CURRENT GRANTS;

-- The administrators' own warehouse, for ad-hoc queries on the account: as small and as
-- short-lived as a warehouse gets. `just sf bootstrap` makes it the default of the person
-- running it when theirs is missing or goes in section 5 (COMPUTE_WH on a trial account).
CREATE WAREHOUSE IF NOT EXISTS WH_PLATFORM
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = True
  INITIALLY_SUSPENDED = True
  COMMENT = 'Warehouse for the account administrators'
;

ALTER WAREHOUSE IF EXISTS WH_PLATFORM SET
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = True
  COMMENT = 'Warehouse for the account administrators'
;

GRANT OWNERSHIP ON WAREHOUSE WH_PLATFORM TO ROLE SYSADMIN COPY CURRENT GRANTS;


-- -----------------------------------------------------------------------------
-- 3. System roles for the Terraform user
-- -----------------------------------------------------------------------------
-- SECURITYADMIN inherits USERADMIN; granting USERADMIN as well lets the provider
-- alias for users (terraform/components/snowflake-account/providers.tf) use it as its primary role.
GRANT ROLE SYSADMIN      TO USER TERRAFORM_USER;
GRANT ROLE SECURITYADMIN TO USER TERRAFORM_USER;
GRANT ROLE USERADMIN     TO USER TERRAFORM_USER;

-- Every provider connection sets the warehouse; SYSADMIN owns it, USERADMIN (and
-- through it SECURITYADMIN) may use it.
GRANT USAGE, OPERATE ON WAREHOUSE WH_PLATFORM_PROVISIONING TO ROLE USERADMIN;

-- Earlier versions provisioned through a custom role, created a database for
-- Terraform state that never lived there (the state is a local file) and capped the
-- warehouse above with a resource monitor of its own. Dropping the role hands
-- whatever it still owned to ACCOUNTADMIN; `just sf bootstrap` then adopts or wipes
-- those objects. Dropping the monitor unassigns it from the warehouse.
DROP ROLE IF EXISTS RL_PLATFORM_PROVISIONING;
DROP DATABASE IF EXISTS DB_PLATFORM_PROVISIONING;
DROP RESOURCE MONITOR IF EXISTS RM_PLATFORM_PROVISIONING;


-- -----------------------------------------------------------------------------
-- 4. Assign Defaults to User
-- -----------------------------------------------------------------------------

ALTER USER IF EXISTS TERRAFORM_USER SET
  DEFAULT_ROLE = SYSADMIN
  DEFAULT_WAREHOUSE = WH_PLATFORM_PROVISIONING
;

-- -----------------------------------------------------------------------------
-- 5. Drop what a fresh account comes with
-- -----------------------------------------------------------------------------
-- A new account ships the COMPUTE_WH warehouse, the SNOWFLAKE_SAMPLE_DATA share and
-- the Snowsight Templates learning environment (SNOWFLAKE_LEARNING_ROLE, _WH, _DB,
-- owned by ACCOUNTADMIN). None of them belongs to the platform, and Terraform has its
-- own warehouse (section 2), as do the administrators (WH_PLATFORM): `just sf bootstrap`
-- makes it the default of the person running it when theirs was COMPUTE_WH; anyone else
-- picks another one. SNOWFLAKE_SAMPLE_DATA comes back any time with
-- CREATE DATABASE SNOWFLAKE_SAMPLE_DATA FROM SHARE SFC_SAMPLES.SAMPLE_DATA.
-- The learning environment is switched off first, or Snowflake provisions it again
-- (https://docs.snowflake.com/en/user-guide/ui-snowsight/snowsight-templates).
SELECT SYSTEM$DISABLE_SNOWFLAKE_LEARNING_ENVIRONMENT();
DROP WAREHOUSE IF EXISTS COMPUTE_WH;
DROP WAREHOUSE IF EXISTS SNOWFLAKE_LEARNING_WH;
DROP DATABASE IF EXISTS SNOWFLAKE_LEARNING_DB;
DROP DATABASE IF EXISTS SNOWFLAKE_SAMPLE_DATA;
DROP ROLE IF EXISTS SNOWFLAKE_LEARNING_ROLE;


-- -----------------------------------------------------------------------------
-- Verification Queries
-- -----------------------------------------------------------------------------
SHOW GRANTS TO USER TERRAFORM_USER;
DESCRIBE USER TERRAFORM_USER;
