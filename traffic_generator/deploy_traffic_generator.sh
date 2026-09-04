#!/bin/bash
set -e

# Deployment script for Cloud Run Traffic Generator & Cloud Scheduler (Every 6 Hours)

ENV_FILE="../.env"
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
elif [ -f ".env" ]; then
    # shellcheck disable=SC1091
    source ".env"
fi

PROJECT_ID="${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT}}"
LOCATION="${LOCATION:-us-central1}"
SERVICE_NAME="legal-agent-traffic-gen"
JOB_NAME="legal-agent-eval-traffic-cron"
SA_NAME="legal-traffic-scheduler-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID is not set."
    exit 1
fi

echo "=== Deploying Traffic Generator Microservice to Cloud Run ==="
echo "Project: $PROJECT_ID | Region: $LOCATION | Service: $SERVICE_NAME"

# Enable required Google Cloud APIs
echo "Ensuring required APIs are enabled..."
gcloud services enable --quiet \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    --project="$PROJECT_ID"

# 1. Create Dedicated Service Account if it does not exist
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Creating service account $SA_NAME..."
    gcloud iam service-accounts create "$SA_NAME" \
        --project="$PROJECT_ID" \
        --display-name="Legal Agent Traffic Scheduler SA" \
        --quiet
    echo "Waiting for service account propagation..."
    sleep 10
fi

# 2. Grant roles to Service Account (Vertex AI User + Cloud Run Invoker + Logging)
echo "Ensuring required IAM roles on service account..."
for i in {1..5}; do
    if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/aiplatform.user" \
        --condition=None \
        --quiet >/dev/null 2>&1 && \
       gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/logging.logWriter" \
        --condition=None \
        --quiet >/dev/null 2>&1; then
        echo "Successfully bound roles/aiplatform.user and roles/logging.logWriter."
        break
    else
        echo "IAM binding attempt $i failed, retrying in 5 seconds..."
        sleep 5
    fi
done

# 3. Deploy container directly from source to Cloud Run
echo "Deploying Cloud Run service from source..."
gcloud run deploy "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$LOCATION" \
    --source="." \
    --port="8080" \
    --service-account="$SA_EMAIL" \
    --set-env-vars="PROJECT_ID=${PROJECT_ID},LOCATION=${LOCATION},REASONING_ENGINE_ID=${REASONING_ENGINE_ID}" \
    --no-allow-unauthenticated \
    --quiet

# 4. Get Cloud Run Service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$LOCATION" \
    --format="value(status.url)")

echo "Cloud Run service deployed at: $SERVICE_URL"

# 5. Grant SA permission to invoke this Cloud Run service
gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$LOCATION" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.invoker" \
    --quiet >/dev/null

# 6. Create or update Cloud Scheduler Job running every 6 hours
TRIGGER_URL="${SERVICE_URL}/run-eval-traffic"
echo "Configuring Cloud Scheduler job to run every 6 hours ($TRIGGER_URL)..."

if gcloud scheduler jobs describe "$JOB_NAME" --project="$PROJECT_ID" --location="$LOCATION" >/dev/null 2>&1; then
    echo "Updating existing Cloud Scheduler job..."
    gcloud scheduler jobs update http "$JOB_NAME" \
        --project="$PROJECT_ID" \
        --location="$LOCATION" \
        --schedule="0 */6 * * *" \
        --uri="$TRIGGER_URL" \
        --http-method="POST" \
        --oidc-service-account-email="$SA_EMAIL" \
        --oidc-token-audience="$SERVICE_URL" \
        --quiet
else
    echo "Creating new Cloud Scheduler job..."
    gcloud scheduler jobs create http "$JOB_NAME" \
        --project="$PROJECT_ID" \
        --location="$LOCATION" \
        --schedule="0 */6 * * *" \
        --uri="$TRIGGER_URL" \
        --http-method="POST" \
        --oidc-service-account-email="$SA_EMAIL" \
        --oidc-token-audience="$SERVICE_URL" \
        --quiet
fi

echo "=== Deployment Complete ==="
echo "Cloud Run Service: $SERVICE_URL"
echo "Scheduled Cron: Every 6 hours (0 */6 * * *)"
echo "To test manually:"
echo "curl -X POST -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" ${TRIGGER_URL}"
