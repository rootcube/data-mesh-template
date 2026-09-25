-- =============================================================================
-- Snowflake Platform Provisioning Setup for Terraform
-- =============================================================================
-- Run this script as ACCOUNTADMIN (`just sf bootstrap` does). Every statement is
-- idempotent, so it is safe to run again on an account that was set up before.
--
-- Terraform provisions through Snowflake's system roles, so every object ends up
-- with the owner Snowflake recommends (see terraform/providers.tf):
--   SYSADMIN       databases, schemas, stages, warehouses
--   SECURITYADMIN  roles and all grants (MANAGE GRANTS)
--   USERADMIN      users
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- -----------------------------------------------------------------------------
-- 0. Account settings
-- -----------------------------------------------------------------------------
-- Account-level defaults; users and sessions can still override most of them.

-- Time: UTC everywhere, so timestamps do not depend on who or what ran the query.
-- TIMESTAMP_NTZ for plain TIMESTAMP columns (Snowflake's default, made explicit).
ALTER ACCOUNT SET
    TIMEZONE               = 'UTC'
    TIMESTAMP_TYPE_MAPPING = 'TIMESTAMP_NTZ'
;

-- Calendar: ISO 8601 weeks, starting on Monday (WEEK_START 1), week 1 being the week
-- with the year's first Thursday (WEEK_OF_YEAR_POLICY 0).
ALTER ACCOUNT SET
    WEEK_START          = 1
    WEEK_OF_YEAR_POLICY = 0
;

-- Output formats: ISO 8601, with millisecond precision and a numeric UTC offset.
ALTER ACCOUNT SET
    DATE_OUTPUT_FORMAT          = 'YYYY-MM-DD'
    TIME_OUTPUT_FORMAT          = 'HH24:MI:SS'
    TIMESTAMP_OUTPUT_FORMAT     = 'YYYY-MM-DD HH24:MI:SS.FF3 TZH:TZM'
    TIMESTAMP_NTZ_OUTPUT_FORMAT = 'YYYY-MM-DD HH24:MI:SS.FF3'
    TIMESTAMP_LTZ_OUTPUT_FORMAT = 'YYYY-MM-DD HH24:MI:SS.FF3 TZH:TZM'
    TIMESTAMP_TZ_OUTPUT_FORMAT  = 'YYYY-MM-DD HH24:MI:SS.FF3 TZH:TZM'
;

-- Security: AES-256 for files PUT into internal stages (default 128), no external
-- stages with inline credentials, and no unloading to URLs typed into a query.
ALTER ACCOUNT SET
    CLIENT_ENCRYPTION_KEY_SIZE                      = 256
    REQUIRE_STORAGE_INTEGRATION_FOR_STAGE_CREATION  = TRUE
    REQUIRE_STORAGE_INTEGRATION_FOR_STAGE_OPERATION = TRUE
    PREVENT_UNLOAD_TO_INLINE_URL                    = TRUE
;

-- Cost guardrail: cancel statements that run longer than 4 hours (default 2 days).
-- Warehouses can set a lower STATEMENT_TIMEOUT_IN_SECONDS of their own.
ALTER ACCOUNT SET
    STATEMENT_TIMEOUT_IN_SECONDS = 14400
;

-- Convenience: cache the MFA token between client connections, full syntax errors.
ALTER ACCOUNT SET
    ALLOW_CLIENT_MFA_CACHING            = TRUE
    ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR = TRUE
;

-- Re-encrypt data older than a year with fresh keys. Needs Enterprise Edition or higher,
-- so the block skips it (and says so) on Standard Edition instead of failing the script.
EXECUTE IMMEDIATE $$
BEGIN
    ALTER ACCOUNT SET PERIODIC_DATA_REKEYING = TRUE;
    RETURN 'PERIODIC_DATA_REKEYING enabled';
EXCEPTION
    WHEN OTHER THEN
        RETURN 'PERIODIC_DATA_REKEYING skipped: ' || SQLERRM;
END;
$$
;


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
-- 2. Create Resource Monitor
-- -----------------------------------------------------------------------------
CREATE RESOURCE MONITOR IF NOT EXISTS RM_PLATFORM_PROVISIONING
  WITH CREDIT_QUOTA = 100
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 75 PERCENT DO NOTIFY
    ON 90 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND
;

ALTER RESOURCE MONITOR IF EXISTS RM_PLATFORM_PROVISIONING SET
    CREDIT_QUOTA = 100
;


-- -----------------------------------------------------------------------------
-- 3. Create Warehouse (owned by SYSADMIN)
-- -----------------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS WH_PLATFORM_PROVISIONING
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = True
  INITIALLY_SUSPENDED = True
  RESOURCE_MONITOR = RM_PLATFORM_PROVISIONING
  COMMENT = 'Warehouse for Terraform platform provisioning'
;

ALTER WAREHOUSE IF EXISTS WH_PLATFORM_PROVISIONING SET
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = True
  RESOURCE_MONITOR = RM_PLATFORM_PROVISIONING
  COMMENT = 'Warehouse for Terraform platform provisioning'
;

GRANT OWNERSHIP ON WAREHOUSE WH_PLATFORM_PROVISIONING TO ROLE SYSADMIN COPY CURRENT GRANTS;


-- -----------------------------------------------------------------------------
-- 4. Create Database for Terraform State/Metadata (owned by SYSADMIN)
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS DB_PLATFORM_PROVISIONING
;

ALTER DATABASE IF EXISTS DB_PLATFORM_PROVISIONING SET
    COMMENT = 'Database for platform provisioning metadata'
;

-- Cleanup Public Schema
DROP SCHEMA IF EXISTS DB_PLATFORM_PROVISIONING.PUBLIC
;

GRANT OWNERSHIP ON DATABASE DB_PLATFORM_PROVISIONING TO ROLE SYSADMIN COPY CURRENT GRANTS;


-- -----------------------------------------------------------------------------
-- 5. System roles for the Terraform user
-- -----------------------------------------------------------------------------
-- SECURITYADMIN inherits USERADMIN; granting USERADMIN as well lets the provider
-- alias for users (terraform/providers.tf) use it as its primary role.
GRANT ROLE SYSADMIN      TO USER TERRAFORM_USER;
GRANT ROLE SECURITYADMIN TO USER TERRAFORM_USER;
GRANT ROLE USERADMIN     TO USER TERRAFORM_USER;

-- Every provider connection sets the warehouse; SYSADMIN owns it, USERADMIN (and
-- through it SECURITYADMIN) may use it.
GRANT USAGE, OPERATE ON WAREHOUSE WH_PLATFORM_PROVISIONING TO ROLE USERADMIN;
GRANT USAGE          ON DATABASE  DB_PLATFORM_PROVISIONING TO ROLE USERADMIN;

-- Earlier versions provisioned through a custom role. Dropping it hands whatever it
-- still owned to ACCOUNTADMIN; `just sf bootstrap` then adopts or wipes those objects.
DROP ROLE IF EXISTS RL_PLATFORM_PROVISIONING;


-- -----------------------------------------------------------------------------
-- 6. Assign Defaults to User
-- -----------------------------------------------------------------------------

ALTER USER IF EXISTS TERRAFORM_USER SET
  DEFAULT_ROLE = SYSADMIN
  DEFAULT_WAREHOUSE = WH_PLATFORM_PROVISIONING
  DEFAULT_NAMESPACE = DB_PLATFORM_PROVISIONING
;

-- -----------------------------------------------------------------------------
-- Verification Queries
-- -----------------------------------------------------------------------------
SHOW GRANTS TO USER TERRAFORM_USER;
DESCRIBE USER TERRAFORM_USER;
SHOW PARAMETERS IN ACCOUNT;
