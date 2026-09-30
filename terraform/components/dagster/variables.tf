# -----------------------------------------------------------------------------
# Input Variables
# -----------------------------------------------------------------------------

# Configuration Path, relative to this component directory (Atmos runs Terraform here)
variable "config_path" {
  description = "Path to the configuration directory containing YAML files"
  type        = string
  default     = "../../config"
}

# -----------------------------------------------------------------------------
# Stack: the deployment of one environment (vars of terraform/stacks/deployments/dagster/<env>.yaml)
# -----------------------------------------------------------------------------

variable "deployment" {
  description = "Name of the deployment: the Helm release, and with the environment the namespace (<deployment>-<env>)"
  type        = string
}

variable "environment" {
  description = "Environment code, as in DB_<PROJECT>_<ENV>: the `code` of a file under config/environments, e.g. prd"
  type        = string
}

variable "dlt_project" {
  description = "Project whose ingest service user runs the dlt code location (and whose source layer it loads)"
  type        = string
}

variable "kube_context" {
  description = "kubeconfig context of the cluster, e.g. k3d-dagster"
  type        = string
}

variable "kube_config_path" {
  description = "kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "image" {
  description = "The code location image (Dockerfile): every code location and every run pod uses it"
  type = object({
    repository  = string
    tag         = string
    pull_policy = string
  })
}

variable "chart_version" {
  description = "Version of the dagster/dagster Helm chart; keep it equal to the dagster version in uv.lock"
  type        = string
  default     = "1.13.24"
}

variable "key_directory" {
  description = "Where the service users' private keys are (`just sf keygen <login>` writes <login>.p8 there)"
  type        = string
  default     = "~/.snowflake/keys"
}

variable "key_revision" {
  description = "Raise it after replacing a private key: the keys are write-only, so Terraform only sends them again on a new revision"
  type        = number
  default     = 1
}

# -----------------------------------------------------------------------------
# Snowflake account (TF_VAR_SNOWFLAKE_* in .env, as for the other components)
# -----------------------------------------------------------------------------

# Mapped to TF_VAR_SNOWFLAKE_ORGANIZATION environment variable
variable "SNOWFLAKE_ORGANIZATION" {
  description = "Snowflake organization name (the part before the dash in <organization>-<account>)"
  type        = string
}

# Mapped to TF_VAR_SNOWFLAKE_ACCOUNT environment variable
variable "SNOWFLAKE_ACCOUNT" {
  description = "Snowflake account name (the part after the dash in <organization>-<account>)"
  type        = string
}
