#!/usr/bin/env bash
# Submit cloudbuild.yaml. This script is not used by tests or CI.
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-agents}"

gcloud builds submit \
  --config cloudbuild.yaml \
  --project "${PROJECT_ID}" \
  --substitutions "_REGION=${REGION},_REPO=${REPO}"
