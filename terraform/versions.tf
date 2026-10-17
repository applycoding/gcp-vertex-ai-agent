terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0.0, < 8.0.0"
    }
  }
}

# Local state on purpose. CI runs `terraform init -backend=false` and
# `terraform validate` with no GCP credentials and no remote backend.
provider "google" {
  project = var.project_id
  region  = var.region
}
