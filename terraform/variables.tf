variable "project_id" {
  description = "GCP project id. Pass -var or a tfvars file when you plan or apply."
  type        = string
}

variable "region" {
  description = "Cloud Run region."
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore location id. nam5 is the usual multi-region location for the default database."
  type        = string
  default     = "nam5"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "vertex-ai-agent"
}

variable "image" {
  description = "Container image URI. Build it with cloudbuild.yaml, then pass the URI here. There is no default image."
  type        = string
}

variable "allow_unauthenticated" {
  description = "Grant roles/run.invoker to allUsers. Leave false until you mean to expose the service."
  type        = bool
  default     = false
}

variable "system_prompt" {
  description = "Initial system prompt stored in Secret Manager. This is demo copy, not a credential."
  type        = string
  default     = "You are the support agent for Northline Outfitters. Use search_catalog, check_stock, and create_support_case. Answer from tool results."
}
