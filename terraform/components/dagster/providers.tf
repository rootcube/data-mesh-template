terraform {
  # Write-only arguments (the private keys in kubernetes_secret_v1.data_wo) need Terraform 1.11.
  required_version = ">= 1.11.0"

  # Pinned to a patch range like the other components: a new minor is a Dependabot pull request.
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9.0"
    }
  }
}

# -----------------------------------------------------------------------------
# The cluster: a context of your kubeconfig (`k3d-dagster` for the local k3d cluster,
# `just k8s up`). The helm provider embeds Helm, so no helm CLI is needed.
# -----------------------------------------------------------------------------

provider "kubernetes" {
  config_path    = pathexpand(var.kube_config_path)
  config_context = var.kube_context
}

provider "helm" {
  kubernetes = {
    config_path    = pathexpand(var.kube_config_path)
    config_context = var.kube_context
  }
}
