#!/bin/bash
set -euo pipefail

# --- Configuration ---
PROJECT_ID=$(gcloud config get-value project)
IMAGE_NAME="bluesky-muted-words-plus"
TAG="latest"
REGION="us-east1"
PORT=8000
SERVICE_NAME="$IMAGE_NAME"
IMAGE_URI="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG}"
ENV_FILE=".env"

# --- Check gcloud auth ---
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
  echo "❌ No active gcloud account found. Run 'gcloud auth login' first."
  exit 1
fi

# --- Enable required services ---
echo "🔧 Enabling required GCP APIs..."
gcloud services enable run.googleapis.com containerregistry.googleapis.com

# --- Build Docker image ---
if docker image inspect "${IMAGE_NAME}:${TAG}" > /dev/null 2>&1; then
  echo "✅ Local image '${IMAGE_NAME}:${TAG}' found. Skipping build."
else
  echo "🔧 Building Docker image '${IMAGE_NAME}:${TAG}'..."
  docker build -t "${IMAGE_NAME}:${TAG}" .
fi

# --- Tag and push to GCR ---
echo "🏷️ Tagging image as ${IMAGE_URI}"
docker tag "${IMAGE_NAME}:${TAG}" "${IMAGE_URI}"

echo "🚀 Pushing image to Google Container Registry..."
docker push "${IMAGE_URI}"

# --- Convert .env to GCP env var format, excluding secrets ---
ENV_VARS=""
if [[ -f "$ENV_FILE" ]]; then
  echo "📄 Loading environment variables from $ENV_FILE"
  ENV_VARS=$(grep -v '^#' "$ENV_FILE" | grep -v -E -e '^\s*HANDLE=|^\s*PASSWORD=' -e '^\s*$' | paste -sd, -)
else
  echo "⚠️ No $ENV_FILE file found. Continuing without env vars."
fi

echo "📄 Here is the app environment: $ENV_VARS"

echo "🚀 Deploying to Cloud Run..."
if [[ -n "$ENV_VARS" ]]; then
  gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_URI" \
    --platform managed \
    --region "$REGION" \
    --port "$PORT" \
    --allow-unauthenticated \
    --set-env-vars "$ENV_VARS"
else
  gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_URI" \
    --platform managed \
    --region "$REGION" \
    --port "$PORT" \
    --allow-unauthenticated
fi

# --- Output URL ---
echo ""
echo "✅ Deployed '$SERVICE_NAME' to Cloud Run!"
gcloud run services describe "$SERVICE_NAME" \
  --platform managed \
  --region "$REGION" \
  --format='value(status.url)'