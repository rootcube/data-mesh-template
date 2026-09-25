# -----------------------------------------------------------------------------
# Stages: the default internal stage of every source layer, where dlt PUTs its
# load files before COPY INTO the source tables (`stage_name` in dlt_pipelines/
# utils/destination.py). One in each shared source layer (`_SRC.ST_DEFAULT`) and one
# in each developer's personal source schema (`<PREFIX>_SRC.ST_DEFAULT`, personal.tf),
# so load files never mix between people. Owned by SYSADMIN; READ/WRITE come from the
# future grants on stages in the layer privileges of the roles, hence the depends_on.
# dbt's on-run-start ALTER STAGE ... REFRESH (dbt_common refresh_stages) runs with READ
# and WRITE ON STAGES, as the engineer role holds on the personal stages; USAGE ON
# STAGES is an external-stage privilege and does not cover these internal stages.
# -----------------------------------------------------------------------------

locals {
  default_stage_name = "ST_DEFAULT"

  source_layer_schemas = {
    for key, layer in local.project_environment_layer_map : key => layer
    if layer.layer_code == "src"
  }

  personal_source_schemas = {
    for key, schema in local.personal_schema_map : key => schema
    if schema.layer_code == "src"
  }
}

resource "snowflake_stage_internal" "default" {
  for_each = local.source_layer_schemas

  database = each.value.database_name
  schema   = module.schema[each.key].schema_name
  name     = local.default_stage_name
  comment  = "Default internal stage of the source layer (dlt PUTs its load files here, then COPY INTO the source tables)"

  # Directory table: SELECT * FROM DIRECTORY(@_SRC.ST_DEFAULT) lists the files. Internal stages do not
  # auto-refresh it (that is an external-stage feature); ALTER STAGE ... REFRESH updates it.
  directory {
    enable = true
  }

  depends_on = [module.schema_grant]
}

resource "snowflake_stage_internal" "personal" {
  for_each = local.personal_source_schemas

  database = each.value.database_name
  schema   = module.personal_schema[each.key].schema_name
  name     = local.default_stage_name
  comment  = "Personal load stage of ${each.value.login} (dlt PUTs its load files here, then COPY INTO the source tables)"

  directory {
    enable = true
  }

  depends_on = [module.personal_schema_grant]
}

output "stage_names" {
  description = "Fully qualified names of the default stages, one per source layer and personal source schema"
  value = sort(concat(
    [for stage in snowflake_stage_internal.default : stage.fully_qualified_name],
    [for stage in snowflake_stage_internal.personal : stage.fully_qualified_name],
  ))
}
