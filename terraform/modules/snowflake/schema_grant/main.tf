# =============================================================================
# Schema Grant Module
# =============================================================================
# Grants privileges on a schema and its objects to a role.
# Supports both existing objects (all) and future objects.

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Locals - Parse privileges into categories
# -----------------------------------------------------------------------------

locals {
  # Schema-level privileges (USAGE, MODIFY, MONITOR, CREATE X, ADD X)
  schema_privileges = [
    for p in var.privileges : p
    if !can(regex(" ON ", p))
  ]

  # Object privilege parsing helper - extracts privilege and object type
  object_privilege_map = {
    for p in var.privileges : p => regex("^(.+) ON (.+)$", p)
    if can(regex(" ON ", p))
  }

  # Table privileges
  table_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "TABLES"
  ]

  # View privileges
  view_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "VIEWS"
  ]

  # Materialized view privileges
  materialized_view_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "MATERIALIZED VIEWS"
  ]

  # Dynamic table privileges
  dynamic_table_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "DYNAMIC TABLES"
  ]

  # External table privileges
  external_table_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "EXTERNAL TABLES"
  ]

  # Iceberg table privileges
  iceberg_table_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "ICEBERG TABLES"
  ]

  # Event table privileges
  event_table_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "EVENT TABLES"
  ]

  # Function privileges
  function_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "FUNCTIONS"
  ]

  # Procedure privileges
  procedure_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "PROCEDURES"
  ]

  # Stage privileges
  stage_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "STAGES"
  ]

  # File format privileges
  file_format_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "FILE FORMATS"
  ]

  # Sequence privileges
  sequence_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "SEQUENCES"
  ]

  # Stream privileges
  stream_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "STREAMS"
  ]

  # Task privileges
  task_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "TASKS"
  ]

  # Pipe privileges
  pipe_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "PIPES"
  ]

  # Alert privileges
  alert_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "ALERTS"
  ]

  # Secret privileges
  secret_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "SECRETS"
  ]

  # Tag privileges
  tag_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "TAGS"
  ]

  # Policy privileges (various types)
  masking_policy_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "MASKING POLICIES"
  ]

  row_access_policy_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "ROW ACCESS POLICIES"
  ]

  password_policy_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "PASSWORD POLICIES"
  ]

  session_policy_privileges = [
    for p, match in local.object_privilege_map : match[0]
    if match[1] == "SESSION POLICIES"
  ]

  # Fully qualified schema name
  fq_schema_name = "\"${var.database_name}\".\"${var.schema_name}\""
}

# -----------------------------------------------------------------------------
# Schema-level grants
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "schema" {
  count = length(local.schema_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.schema_privileges

  on_schema {
    schema_name = local.fq_schema_name
  }
}

# -----------------------------------------------------------------------------
# Table grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "tables_all" {
  count = length(local.table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.table_privileges

  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "tables_future" {
  count = length(local.table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.table_privileges

  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# View grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "views_all" {
  count = length(local.view_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.view_privileges

  on_schema_object {
    all {
      object_type_plural = "VIEWS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "views_future" {
  count = length(local.view_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.view_privileges

  on_schema_object {
    future {
      object_type_plural = "VIEWS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Materialized View grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "materialized_views_all" {
  count = length(local.materialized_view_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.materialized_view_privileges

  on_schema_object {
    all {
      object_type_plural = "MATERIALIZED VIEWS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "materialized_views_future" {
  count = length(local.materialized_view_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.materialized_view_privileges

  on_schema_object {
    future {
      object_type_plural = "MATERIALIZED VIEWS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Dynamic Table grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "dynamic_tables_all" {
  count = length(local.dynamic_table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.dynamic_table_privileges

  on_schema_object {
    all {
      object_type_plural = "DYNAMIC TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "dynamic_tables_future" {
  count = length(local.dynamic_table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.dynamic_table_privileges

  on_schema_object {
    future {
      object_type_plural = "DYNAMIC TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# External Table grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "external_tables_all" {
  count = length(local.external_table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.external_table_privileges

  on_schema_object {
    all {
      object_type_plural = "EXTERNAL TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "external_tables_future" {
  count = length(local.external_table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.external_table_privileges

  on_schema_object {
    future {
      object_type_plural = "EXTERNAL TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Iceberg Table grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "iceberg_tables_all" {
  count = length(local.iceberg_table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.iceberg_table_privileges

  on_schema_object {
    all {
      object_type_plural = "ICEBERG TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "iceberg_tables_future" {
  count = length(local.iceberg_table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.iceberg_table_privileges

  on_schema_object {
    future {
      object_type_plural = "ICEBERG TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Event Table grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "event_tables_all" {
  count = length(local.event_table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.event_table_privileges

  on_schema_object {
    all {
      object_type_plural = "EVENT TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "event_tables_future" {
  count = length(local.event_table_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.event_table_privileges

  on_schema_object {
    future {
      object_type_plural = "EVENT TABLES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Function grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "functions_all" {
  count = length(local.function_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.function_privileges

  on_schema_object {
    all {
      object_type_plural = "FUNCTIONS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "functions_future" {
  count = length(local.function_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.function_privileges

  on_schema_object {
    future {
      object_type_plural = "FUNCTIONS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Procedure grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "procedures_all" {
  count = length(local.procedure_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.procedure_privileges

  on_schema_object {
    all {
      object_type_plural = "PROCEDURES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "procedures_future" {
  count = length(local.procedure_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.procedure_privileges

  on_schema_object {
    future {
      object_type_plural = "PROCEDURES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Stage grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "stages_all" {
  count = length(local.stage_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.stage_privileges

  on_schema_object {
    all {
      object_type_plural = "STAGES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "stages_future" {
  count = length(local.stage_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.stage_privileges

  on_schema_object {
    future {
      object_type_plural = "STAGES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# File Format grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "file_formats_all" {
  count = length(local.file_format_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.file_format_privileges

  on_schema_object {
    all {
      object_type_plural = "FILE FORMATS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "file_formats_future" {
  count = length(local.file_format_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.file_format_privileges

  on_schema_object {
    future {
      object_type_plural = "FILE FORMATS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Sequence grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "sequences_all" {
  count = length(local.sequence_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.sequence_privileges

  on_schema_object {
    all {
      object_type_plural = "SEQUENCES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "sequences_future" {
  count = length(local.sequence_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.sequence_privileges

  on_schema_object {
    future {
      object_type_plural = "SEQUENCES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Stream grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "streams_all" {
  count = length(local.stream_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.stream_privileges

  on_schema_object {
    all {
      object_type_plural = "STREAMS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "streams_future" {
  count = length(local.stream_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.stream_privileges

  on_schema_object {
    future {
      object_type_plural = "STREAMS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Task grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "tasks_all" {
  count = length(local.task_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.task_privileges

  on_schema_object {
    all {
      object_type_plural = "TASKS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "tasks_future" {
  count = length(local.task_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.task_privileges

  on_schema_object {
    future {
      object_type_plural = "TASKS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Pipe grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "pipes_all" {
  count = length(local.pipe_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.pipe_privileges

  on_schema_object {
    all {
      object_type_plural = "PIPES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "pipes_future" {
  count = length(local.pipe_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.pipe_privileges

  on_schema_object {
    future {
      object_type_plural = "PIPES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Alert grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "alerts_all" {
  count = length(local.alert_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.alert_privileges

  on_schema_object {
    all {
      object_type_plural = "ALERTS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "alerts_future" {
  count = length(local.alert_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.alert_privileges

  on_schema_object {
    future {
      object_type_plural = "ALERTS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Secret grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "secrets_all" {
  count = length(local.secret_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.secret_privileges

  on_schema_object {
    all {
      object_type_plural = "SECRETS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "secrets_future" {
  count = length(local.secret_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.secret_privileges

  on_schema_object {
    future {
      object_type_plural = "SECRETS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Tag grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "tags_all" {
  count = length(local.tag_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.tag_privileges

  on_schema_object {
    all {
      object_type_plural = "TAGS"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "tags_future" {
  count = length(local.tag_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.tag_privileges

  on_schema_object {
    future {
      object_type_plural = "TAGS"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Masking Policy grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "masking_policies_all" {
  count = length(local.masking_policy_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.masking_policy_privileges

  on_schema_object {
    all {
      object_type_plural = "MASKING POLICIES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "masking_policies_future" {
  count = length(local.masking_policy_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.masking_policy_privileges

  on_schema_object {
    future {
      object_type_plural = "MASKING POLICIES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Row Access Policy grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "row_access_policies_all" {
  count = length(local.row_access_policy_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.row_access_policy_privileges

  on_schema_object {
    all {
      object_type_plural = "ROW ACCESS POLICIES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "row_access_policies_future" {
  count = length(local.row_access_policy_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.row_access_policy_privileges

  on_schema_object {
    future {
      object_type_plural = "ROW ACCESS POLICIES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Password Policy grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "password_policies_all" {
  count = length(local.password_policy_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.password_policy_privileges

  on_schema_object {
    all {
      object_type_plural = "PASSWORD POLICIES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "password_policies_future" {
  count = length(local.password_policy_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.password_policy_privileges

  on_schema_object {
    future {
      object_type_plural = "PASSWORD POLICIES"
      in_schema          = local.fq_schema_name
    }
  }
}

# -----------------------------------------------------------------------------
# Session Policy grants (all + future)
# -----------------------------------------------------------------------------

resource "snowflake_grant_privileges_to_account_role" "session_policies_all" {
  count = length(local.session_policy_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.session_policy_privileges

  on_schema_object {
    all {
      object_type_plural = "SESSION POLICIES"
      in_schema          = local.fq_schema_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "session_policies_future" {
  count = length(local.session_policy_privileges) > 0 ? 1 : 0

  account_role_name = var.role_name
  privileges        = local.session_policy_privileges

  on_schema_object {
    future {
      object_type_plural = "SESSION POLICIES"
      in_schema          = local.fq_schema_name
    }
  }
}
