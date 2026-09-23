-- =============================================================================
-- Snowflake Platform Provisioning Setup for Terraform
-- =============================================================================
-- Run this script as ACCOUNTADMIN
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- -----------------------------------------------------------------------------
-- 0. Configure some Global Account Settings
-- -----------------------------------------------------------------------------

ALTER ACCOUNT SET ALLOW_CLIENT_MFA_CACHING = TRUE;
ALTER ACCOUNT SET ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR = TRUE;

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
-- 3. Create Warehouse
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


-- -----------------------------------------------------------------------------
-- 4. Create Role
-- -----------------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS RL_PLATFORM_PROVISIONING
;

ALTER ROLE IF EXISTS RL_PLATFORM_PROVISIONING SET
    COMMENT = 'Role for Terraform to manage Snowflake infrastructure'
;

GRANT ROLE RL_PLATFORM_PROVISIONING TO USER TERRAFORM_USER;


-- -----------------------------------------------------------------------------
-- 5. Create Database for Terraform State/Metadata
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS DB_PLATFORM_PROVISIONING
;

ALTER DATABASE IF EXISTS DB_PLATFORM_PROVISIONING SET
    COMMENT = 'Database for platform provisioning metadata'
;

-- Cleanup Public Schema
DROP SCHEMA IF EXISTS DB_PLATFORM_PROVISIONING.PUBLIC
;


-- -----------------------------------------------------------------------------
-- 6. Grant Account-Level Privileges to Role
-- -----------------------------------------------------------------------------

-- User management
GRANT CREATE USER               ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;
GRANT MANAGE GRANTS             ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- Role management
GRANT CREATE ROLE               ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- Database management
GRANT CREATE DATABASE           ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- Warehouse management
GRANT CREATE WAREHOUSE          ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- Resource monitor management (not supported)
--GRANT CREATE RESOURCE MONITOR   ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- Integration management
GRANT CREATE INTEGRATION        ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- Network policy management
GRANT CREATE NETWORK POLICY     ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- Share management
GRANT CREATE SHARE              ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;
GRANT IMPORT SHARE              ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- Account monitoring
GRANT MONITOR USAGE             ON ACCOUNT TO ROLE RL_PLATFORM_PROVISIONING;

-- The provider needs a warehouse for its own queries and its default database
GRANT USAGE, OPERATE            ON WAREHOUSE WH_PLATFORM_PROVISIONING TO ROLE RL_PLATFORM_PROVISIONING;
GRANT USAGE                     ON DATABASE DB_PLATFORM_PROVISIONING TO ROLE RL_PLATFORM_PROVISIONING;


-- -----------------------------------------------------------------------------
-- 7. Assign Defaults to User
-- -----------------------------------------------------------------------------

ALTER USER IF EXISTS TERRAFORM_USER SET
  DEFAULT_ROLE = RL_PLATFORM_PROVISIONING
  DEFAULT_WAREHOUSE = WH_PLATFORM_PROVISIONING
  DEFAULT_NAMESPACE = DB_PLATFORM_PROVISIONING
;

-- -----------------------------------------------------------------------------
-- Verification Queries
-- -----------------------------------------------------------------------------
SHOW GRANTS TO ROLE RL_PLATFORM_PROVISIONING;
SHOW GRANTS TO USER TERRAFORM_USER;
DESCRIBE USER TERRAFORM_USER;
