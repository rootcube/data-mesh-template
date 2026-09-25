# -----------------------------------------------------------------------------
# Stages: the default internal stage of every source layer, where dlt PUTs its
# load files before COPY INTO the source tables (`stage_name` in dlt_pipelines/
# utils/destination.py). READ/WRITE come from the layer privileges of the roles.
# -----------------------------------------------------------------------------

locals {
  default_stage_name = "ST_DEFAULT"

  source_layer_schemas = {
    for key, layer in local.project_environment_layer_map : key => layer
    if layer.layer_code == "src"
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
}

output "stage_names" {
  description = "Fully qualified names of the default stages, one per source layer"
  value       = sort([for stage in snowflake_stage_internal.default : stage.fully_qualified_name])
}
