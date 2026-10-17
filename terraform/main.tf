locals {
  agent_roles = [
    "roles/aiplatform.user",
    "roles/datastore.user",
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor",
  ]
}

resource "google_project_service" "required" {
  for_each = toset([
    "run.googleapis.com",
    "firestore.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "agent" {
  project      = var.project_id
  account_id   = "vertex-ai-agent"
  display_name = "Vertex AI retail agent"
}

resource "google_project_iam_member" "agent" {
  for_each = toset(local.agent_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_firestore_database" "catalog" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  delete_protection_state = "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "ABANDON"

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "prompt" {
  project   = var.project_id
  secret_id = "agent-system-prompt"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "prompt" {
  secret      = google_secret_manager_secret.prompt.id
  secret_data = var.system_prompt
}

resource "google_cloud_run_v2_service" "agent" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  labels = {
    app = "vertex-ai-agent"
  }

  template {
    service_account = google_service_account.agent.email
    timeout         = "60s"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }

      env {
        name  = "MODEL_BACKEND"
        value = "vertex"
      }

      env {
        name  = "STORE_BACKEND"
        value = "firestore"
      }

      env {
        name  = "GEMINI_MODEL"
        value = "gemini-2.5-flash"
      }

      env {
        name  = "SECRET_MANAGER_ENABLED"
        value = "true"
      }

      env {
        name  = "AGENT_PROMPT_SECRET"
        value = google_secret_manager_secret.prompt.secret_id
      }

      env {
        name  = "CLOUD_LOGGING_CLIENT"
        value = "false"
      }

      startup_probe {
        http_get {
          path = "/health"
        }

        initial_delay_seconds = 0
        timeout_seconds       = 1
        period_seconds        = 5
        failure_threshold     = 6
      }
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_version.prompt,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.allow_unauthenticated ? 1 : 0

  project  = google_cloud_run_v2_service.agent.project
  location = google_cloud_run_v2_service.agent.location
  name     = google_cloud_run_v2_service.agent.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
