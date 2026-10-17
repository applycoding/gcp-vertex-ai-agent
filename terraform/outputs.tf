output "service_url" {
  description = "HTTPS URL of the Cloud Run service."
  value       = google_cloud_run_v2_service.agent.uri
}

output "service_account_email" {
  description = "Runtime service account."
  value       = google_service_account.agent.email
}

output "firestore_database" {
  description = "Firestore database id."
  value       = google_firestore_database.catalog.name
}

output "prompt_secret" {
  description = "Secret Manager id of the system prompt."
  value       = google_secret_manager_secret.prompt.secret_id
}
