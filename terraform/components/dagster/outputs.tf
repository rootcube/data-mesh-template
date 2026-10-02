# =============================================================================
# Component Outputs: the Dagster deployment of one environment
# =============================================================================

output "namespace" {
  description = "Kubernetes namespace of the deployment"
  value       = kubernetes_namespace_v1.dagster.metadata[0].name
}

output "code_locations" {
  description = "Code location -> Dagster module and the Snowflake identity it runs as"
  value = {
    for name, location in local.locations : name => {
      module    = location.module
      user      = local.identities[name].login
      role      = local.identities[name].role
      warehouse = local.identities[name].warehouse
    }
  }
}
