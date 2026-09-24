# -----------------------------------------------------------------------------
# Stages: one internal stage per source layer, where dlt PUTs its load files
# before COPY INTO the source tables (`stage_name` in dlt_pipelines/utils/
# destination.py). READ/WRITE come from the layer privileges of the roles.
# -----------------------------------------------------------------------------

locals {
  dlt_stage_name = "ST_DLT"

  source_layer_schemas = {
    for key, layer in local.project_environment_layer_map : key => layer
    if layer.layer_code == "src"
  }
}

resource "snowflake_stage_internal" "dlt" {
  for_each = local.source_layer_schemas

  database = each.value.database_name
  schema   = module.schema[each.key].schema_name
  name     = local.dlt_stage_name
  comment  = "Internal stage for dlt load files (PUT, then COPY INTO the source tables)"
}

output "stage_names" {
  description = "Fully qualified names of the dlt stages, one per source layer"
  value       = sort([for stage in snowflake_stage_internal.dlt : stage.fully_qualified_name])
}
