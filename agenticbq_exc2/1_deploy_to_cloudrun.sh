#!/bin/bash
set -e

# Export variables from .env file if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

export APP_NAME="${AGENT_APP_NAME:-countwords}"
export REGION="${GOOGLE_CLOUD_HOSTING_LOCATION:-europe-west4}"
export PROJECT="${GOOGLE_CLOUD_PROJECT:-genai-app-builder}"

echo "============================================================"
echo "Deploying ADK Agent '${APP_NAME}' to Cloud Run in ${REGION}"
echo "Project: ${PROJECT}"
echo "============================================================"

# Option A: Deploy using agents-cli
# agents-cli deploy --deployment-target cloud_run --service-name "${APP_NAME}"

# Option B: Deploy using gcloud run deploy directly from source
gcloud run deploy "${APP_NAME}" \
  --source . \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=1,GOOGLE_GENAI_USE_ENTERPRISE=true,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=global,MODEL=gemini-3.8-flash,AGENT_APP_NAME=${APP_NAME}" \
  --allow-unauthenticated

SERVICE_URL=$(gcloud run services describe "${APP_NAME}" --platform managed --region "${REGION}" --project "${PROJECT}" --format 'value(status.url)')

echo "============================================================"
echo "Deployment Complete!"
echo "Cloud Run Service URL: ${SERVICE_URL}"
echo "BigQuery Endpoint:     ${SERVICE_URL}/trigger/bq (or ${SERVICE_URL}/)"
echo "============================================================"
