#!/bin/bash
set -euo pipefail

# --- Configuration ---
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
IMAGE_NAME="bluesky-muted-words-plus"
TAG="latest"
REGION="us-east1"
PORT=8000
SERVICE_NAME="$IMAGE_NAME"
IMAGE_URI="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG}"
ENV_FILE=".env"

# --- Convert .env to GCP env var format, excluding secrets ---
ENV_VARS=""
if [[ -f "$ENV_FILE" ]]; then
  ENV_VARS=$(grep -v -E -e '^\s*HANDLE=|^\s*PASSWORD=|^\s*PORT=' -e '^\s*$' -e '^#' "$ENV_FILE" | paste -sd, -)
fi

function build() {
  # --- Clean SQLite database ---
  echo "🧹 Cleaning up feed_database.db (Post & PostVector)..."
  if [[ -f "feed_database.db" ]]; then
    sqlite3 feed_database.db <<EOF
DELETE FROM PostVector;
DELETE FROM Post;
VACUUM;
EOF
    echo "✅ SQLite cleanup complete."
  else
    echo "⚠️ feed_database.db not found. Skipping SQLite cleanup."
  fi
  # --- Build Docker image ---
  echo "🔧 Building Docker image '${IMAGE_NAME}:${TAG}'..."
  docker build -t "${IMAGE_NAME}:${TAG}" .

  # --- Tag Docker Image ---
  echo "🏷️ Tagging image as ${IMAGE_URI}"
  docker tag "${IMAGE_NAME}:${TAG}" "${IMAGE_URI}"
}

function push() {
  # --- Push image to GCP ---
  echo "🚀 Pushing image to Google Container Registry..."
  docker push "${IMAGE_URI}"
}

function deploy() {
  echo "🚀 Deploying to Cloud Run..."
  if [[ -n "$ENV_VARS" ]]; then
    gcloud run deploy "$SERVICE_NAME" \
      --image "$IMAGE_URI" \
      --platform managed \
      --region "$REGION" \
      --port "$PORT" \
      --cpu=2 \
      --memory="4Gi" \
      --allow-unauthenticated \
      --set-env-vars "$ENV_VARS"
  else
    gcloud run deploy "$SERVICE_NAME" \
      --image "$IMAGE_URI" \
      --platform managed \
      --region "$REGION" \
      --port "$PORT" \
      --cpu=2 \
      --memory="4Gi" \
      --allow-unauthenticated
  fi
  # --- Output URL ---
  echo ""
  echo "✅ Deployed '$SERVICE_NAME' to Cloud Run!"
  gcloud run services describe "$SERVICE_NAME" \
    --platform managed \
    --region "$REGION" \
    --format='value(status.url)'
}

function usage() {
  echo "Usage: $0 [OPTIONS]"
  echo "Options:"
  echo "  -b, --build     Build the Docker image"
  echo "  -p, --push      Push the image to GCP"
  echo "  -d, --deploy    Deploy the service to Cloud Run"
  echo "  -h, --help      Show this help message"
  exit 0
}

function main() {

  local DO_BUILD=false
  local DO_PUSH=false
  local DO_DEPLOY=false

  # --- Parse long options ---
  TEMP=$(getopt -o bpdh --long build,push,deploy,help -n "$0" -- "$@")
  if [[ $? != 0 ]]; then
    echo "❌ Failed to parse options." >&2
    exit 1
  fi
  eval set -- "$TEMP"

  while true; do
    case "$1" in
      -b|--build)   DO_BUILD=true; shift ;;
      -p|--push)    DO_PUSH=true; shift ;;
      -d|--deploy)  DO_DEPLOY=true; shift ;;
      -h|--help)    usage ;;
      --)           shift; break ;;
      *)            echo "❌ Unknown option: $1"; usage ;;
    esac
  done

  if ! $DO_BUILD && ! $DO_PUSH && ! $DO_DEPLOY; then
    usage
  fi

  echo "📄 Here is the app environment: $ENV_VARS"

  # --- Check gcloud auth ---
  if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo "❌ No active gcloud account found. Run 'gcloud auth login' first."
    exit 1
  fi
  # --- Enable required services ---
  echo "🔧 Enabling required GCP APIs..."
  gcloud services enable run.googleapis.com containerregistry.googleapis.com

  $DO_BUILD && build
  $DO_PUSH && push
  $DO_DEPLOY && deploy

}

main "$@"