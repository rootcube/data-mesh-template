-- =============================================================================
-- Snowflake Account Settings
-- =============================================================================
-- Run this script as ACCOUNTADMIN. `just sf bootstrap` lists the parameters and
-- asks before running it (--account-settings ask|apply|skip). Every statement is
-- idempotent, so it is safe to run again.
--
-- Account-level defaults; users and sessions can still override most of them.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

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
-- Opt in: convenience that weakens a security default (commented out on purpose)
-- -----------------------------------------------------------------------------
-- Both apply to the whole account, so the bootstrap does not set them. Uncomment only
-- deliberately, and prefer the narrower route named with each.
--
-- ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR: Snowflake stops redacting the failing SQL, so literals
-- from a WHERE or INSERT show up in error messages and in the query history. While debugging:
-- ALTER SESSION SET ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR = TRUE;
--
-- ALLOW_CLIENT_MFA_CACHING: clients reuse an MFA token instead of prompting per connection, so a
-- stolen token logs in until it expires. Account level only, no session equivalent; the service
-- users here authenticate with a key pair and need neither.
--
-- ALTER ACCOUNT SET
--     ALLOW_CLIENT_MFA_CACHING             = TRUE
--     ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR = TRUE
-- ;

-- -----------------------------------------------------------------------------
-- Verification Queries
-- -----------------------------------------------------------------------------
SHOW PARAMETERS IN ACCOUNT;
