# -----------------------------------------------------------------------------
# Dagster on Kubernetes: one environment of the platform
# -----------------------------------------------------------------------------
#
# The official Dagster Helm chart (webserver, daemon, Postgres, K8sRunLauncher) with one
# code location per concern, as workspace.yaml has them for `dagster dev`: `dlt`, and
# `dbt-<project>` for every project in this environment. Each location, and every run it
# launches in a pod of its own, signs in to Snowflake as a service user from config/users
# (`type: service`): dlt as the ingest user of `dlt_project`, dbt as the transform user of
# its project. Their private keys go into Kubernetes secrets write-only, never into the state.
#
# One Atmos stack per environment: terraform/stacks/deployments/dagster/<env>.yaml.
#
# -----------------------------------------------------------------------------

module "config" {
  source      = "../../modules/config"
  config_path = var.config_path
}

locals {
  namespace = "${var.deployment}-${var.environment}"

  # The environment key of this stack's environment code (var.environment is the code, as in DB_<PROJECT>_<ENV>)
  environment_key = one([for key, code in module.config.environment_codes : key if code == var.environment])
  projects        = { for key, project in module.config.projects : key => project if contains(project.environments, local.environment_key) }

  # "<project>/<role>" -> the login of the service user holding that project role in this environment
  service_logins = {
    for grant in flatten([
      for key, user in module.config.users : [
        for assignment in user.roles : {
          id    = "${assignment.project}/${assignment.role}"
          login = user.login
        }
        if contains(keys(local.projects), assignment.project) && (
          can(tostring(assignment.environments)) && assignment.environments == "*" ||
          contains(try(tolist(assignment.environments), local.projects[assignment.project].environments), local.environment_key)
        )
      ]
      if try(user.type, "person") == "service" && !try(user.disabled, false)
    ]) : grant.id => grant.login...
  }

  # The code locations: Dagster module, the project whose database they work in, the system role they run as
  locations = merge(
    { dlt = { module = "orchestrator.locations.dlt.definitions", project = var.dlt_project, role = "ingest" } },
    {
      for key in keys(local.projects) : "dbt-${replace(key, "_", "-")}" => {
        module  = "orchestrator.locations.dbt.dbt_${key}.definitions"
        project = key
        role    = "transform"
      }
    }
  )

  # Per location: the service user and the Snowflake objects its role works with
  identities = {
    for name, location in local.locations : name => {
      login     = try(local.service_logins["${location.project}/${location.role}"][0], null)
      role      = upper("RL_${location.project}_${var.environment}__${module.config.role_codes[location.role]}")
      warehouse = upper("WH_${location.project}_${var.environment}")
      database  = upper("DB_${location.project}_${var.environment}")
    }
  }
  missing_identities = [for name, location in local.locations : "${location.role} of ${location.project} (${name})" if local.identities[name].login == null]

  logins       = toset([for identity in local.identities : identity.login if identity.login != null])
  secret_names = { for login in local.logins : login => "snowflake-${lower(replace(login, "_", "-"))}" }
  key_mount    = "/var/secrets/snowflake"
  key_file     = "private_key.p8"
}

resource "kubernetes_namespace_v1" "dagster" {
  metadata {
    name = local.namespace
  }
}

# -----------------------------------------------------------------------------
# Private keys: ~/.snowflake/keys/<login>.p8 into one secret per service user, write-only
# -----------------------------------------------------------------------------

resource "kubernetes_secret_v1" "snowflake_key" {
  for_each = local.logins

  metadata {
    name      = local.secret_names[each.key]
    namespace = kubernetes_namespace_v1.dagster.metadata[0].name
  }

  data_wo          = { (local.key_file) = fileexists(pathexpand("${var.key_directory}/${each.key}.p8")) ? file(pathexpand("${var.key_directory}/${each.key}.p8")) : "" }
  data_wo_revision = var.key_revision

  lifecycle {
    precondition {
      condition     = fileexists(pathexpand("${var.key_directory}/${each.key}.p8"))
      error_message = "No private key ${var.key_directory}/${each.key}.p8: run `just sf keygen ${each.key}` and put the public key it prints into the user file (rsa_public_key)."
    }
  }
}

# -----------------------------------------------------------------------------
# The Dagster chart
# -----------------------------------------------------------------------------

# Set before the chart's Postgres first creates its volume: the volume keeps the password it was created with.
resource "random_password" "postgresql" {
  length  = 32
  special = false
}

locals {
  user_deployments = [
    for name, location in local.locations : {
      name  = name
      image = { repository = var.image.repository, tag = var.image.tag, pullPolicy = var.image.pull_policy }
      # `dagster code-server start`: definitions reload from the UI without restarting the pod
      codeServerArgs = ["-m", location.module]
      port           = 3030
      env = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "SNOWFLAKE_ACCOUNT", value = "${var.SNOWFLAKE_ORGANIZATION}-${var.SNOWFLAKE_ACCOUNT}" },
        { name = "SNOWFLAKE_USER", value = local.identities[name].login },
        { name = "SNOWFLAKE_ROLE", value = local.identities[name].role },
        { name = "SNOWFLAKE_WAREHOUSE", value = local.identities[name].warehouse },
        { name = "SNOWFLAKE_DATABASE", value = local.identities[name].database },
        { name = "SNOWFLAKE_SCHEMA", value = "" },
        { name = "SNOWFLAKE_PRIVATE_KEY_PATH", value = "${local.key_mount}/${local.key_file}" },
      ]
      volumes      = [{ name = "snowflake-key", secret = { secretName = try(local.secret_names[local.identities[name].login], "") } }]
      volumeMounts = [{ name = "snowflake-key", mountPath = local.key_mount, readOnly = true }]
      # Run pods get the location's environment, secret and volume: the same identity
      includeConfigInLaunchedRuns = { enabled = true }
    }
  ]

  values = {
    telemetry = { enabled = false }
    # The webserver and the daemon run the chart's own image; pulled once, then kept
    dagsterWebserver = { image = { pullPolicy = "IfNotPresent" } }
    dagsterDaemon    = { image = { pullPolicy = "IfNotPresent" } }
    runLauncher = {
      type   = "K8sRunLauncher"
      config = { k8sRunLauncher = { imagePullPolicy = var.image.pull_policy } }
    }
    postgresql = {
      enabled            = true
      postgresqlPassword = random_password.postgresql.result
    }
    "dagster-user-deployments" = {
      enabled     = true
      deployments = local.user_deployments
    }
  }
}

resource "helm_release" "dagster" {
  name       = var.deployment
  namespace  = kubernetes_namespace_v1.dagster.metadata[0].name
  repository = "https://dagster-io.github.io/helm"
  chart      = "dagster"
  version    = var.chart_version
  values     = [yamlencode(local.values)]
  # The first install pulls the chart's images and Postgres initializes its volume
  timeout = 900

  depends_on = [kubernetes_secret_v1.snowflake_key]

  lifecycle {
    precondition {
      condition     = local.environment_key != null
      error_message = "Stack ${var.deployment}-${var.environment}: no environment with code ${var.environment} in config/environments."
    }
    precondition {
      condition     = length(local.missing_identities) == 0
      error_message = "No service user (config/users, type: service) holds the ${join(", ", local.missing_identities)} in environment ${var.environment}."
    }
  }
}
