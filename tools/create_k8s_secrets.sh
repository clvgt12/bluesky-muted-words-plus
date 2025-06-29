#!/bin/bash

# This script automates the creation/update of Kubernetes Secrets for both
# PostgreSQL credentials and Google Cloud Service Account keys.

# --- Configuration for PostgreSQL Credentials Secret ---
ENV_FILE="./.env.development" # Path to your .env.development file
K8S_NAMESPACE="bluesky-muted-words-plus" # Your target Kubernetes namespace
POSTGRES_SECRET_NAME="postgres-credentials" # Name of the Kubernetes Secret for Postgres

# --- Configuration for Google Cloud Service Account Key Secret ---
# IMPORTANT: Replace <YOUR_GCP_PROJECT_ID> with your actual Google Cloud Project ID
GCP_PROJECT_ID="bluesky-muted-words-plus" # <<<< IMPORTANT: SET YOUR GCP PROJECT ID HERE
GCP_SA_NAME="minikube-bluesky-sa" # Name for the new Google Cloud Service Account
GCP_SA_EMAIL="${GCP_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
GCP_SA_KEY_FILE="./${GCP_SA_NAME}-key.json" # Local path where the SA JSON key will be saved
GCP_SECRET_NAME="google-application-credentials" # Name of the Kubernetes Secret for GCP credentials

# --- Helper function for error handling ---
handle_error() {
  echo "Error: $1" >&2
  exit 1
}

# --- Check for .env file existence ---
if [ ! -f "$ENV_FILE" ]; then
  handle_error ".env.development file not found at $ENV_FILE. Please ensure the file exists and the path is correct."
fi

# --- Ensure the Kubernetes namespace exists ---
echo "Ensuring Kubernetes namespace '$K8S_NAMESPACE' exists..."
kubectl create namespace "$K8S_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - || handle_error "Failed to ensure namespace '$K8S_NAMESPACE' exists."

# --- Delete existing PostgreSQL secret (optional, but ensures a clean slate) ---
echo "Deleting existing secret '$POSTGRES_SECRET_NAME' in namespace '$K8S_NAMESPACE' (if it exists)..."
kubectl delete secret "$POSTGRES_SECRET_NAME" --ignore-not-found -n "$K8S_NAMESPACE"

# --- Extract PostgreSQL variables from .env.development ---
echo "Extracting PostgreSQL variables from $ENV_FILE..."
POSTGRES_USER_VAL=$(awk -F'=' '/^POSTGRES_USER=/{print $2}' "$ENV_FILE")
POSTGRES_DB_VAL=$(awk -F'=' '/^POSTGRES_DB=/{print $2}' "$ENV_FILE")
POSTGRES_PASSWORD_VAL=$(awk -F'=' '/^POSTGRES_PASSWORD=/{print $2}' "$ENV_FILE")
BSKY_HANDLE_VAL=$(awk -F'=' '/^HANDLE=/{print $2}' "$ENV_FILE")
BSKY_APP_PASSWORD_VAL=$(awk -F'=' '/^PASSWORD=/{print $2}' "$ENV_FILE")

# --- Basic Validation of extracted PostgreSQL values ---
[ -z "$POSTGRES_USER_VAL" ] && handle_error "POSTGRES_USER not found or empty in $ENV_FILE"
[ -z "$POSTGRES_DB_VAL" ] && handle_error "POSTGRES_DB not found or empty in $ENV_FILE"
[ -z "$POSTGRES_PASSWORD_VAL" ] && handle_error "POSTGRES_PASSWORD not found or empty in $ENV_FILE"
[ -z "$BSKY_HANDLE_VAL" ] && handle_error "HANDLE (BSky username) not found or empty in $ENV_FILE"
[ -z "$BSKY_APP_PASSWORD_VAL" ] && handle_error "PASSWORD (BSky app password) not found or empty in $ENV_FILE"

# --- Create/Update the Kubernetes Secret for PostgreSQL ---
echo "Creating/updating Kubernetes Secret '$POSTGRES_SECRET_NAME' in namespace '$K8S_NAMESPACE'..."
kubectl create secret generic "$POSTGRES_SECRET_NAME" \
  --from-literal=username="$POSTGRES_USER_VAL" \
  --from-literal=password="$POSTGRES_PASSWORD_VAL" \
  --from-literal=database="$POSTGRES_DB_VAL" \
  --from-literal=handle="$BSKY_HANDLE_VAL" \
  --from-literal=bsky_password="$BSKY_APP_PASSWORD_VAL" \
  --namespace="$K8S_NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f - || handle_error "Failed to create/update Postgres secret."

echo "Kubernetes Secret '$POSTGRES_SECRET_NAME' created/updated successfully."

# --- Google Cloud Service Account and Key Management ---

# Delete existing GCP Service Account key file if it exists locally
echo "Deleting existing local GCP Service Account key file: $GCP_SA_KEY_FILE (if it exists)..."
rm -f "$GCP_SA_KEY_FILE"

# Delete existing Kubernetes Secret for GCP credentials
echo "Deleting existing Kubernetes Secret '$GCP_SECRET_NAME' in namespace '$K8S_NAMESPACE' (if it exists)..."
kubectl delete secret "$GCP_SECRET_NAME" --ignore-not-found -n "$K8S_NAMESPACE"

# Create Google Cloud Service Account if it doesn't exist
echo "Checking if Google Cloud Service Account '$GCP_SA_NAME' already exists..."
if ! gcloud iam service-accounts describe "$GCP_SA_EMAIL" --project="$GCP_PROJECT_ID" &> /dev/null; then
  echo "Creating Google Cloud Service Account '$GCP_SA_NAME' in project '$GCP_PROJECT_ID'..."
  gcloud iam service-accounts create "$GCP_SA_NAME" \
    --display-name="Minikube Bluesky Service Account" \
    --project="$GCP_PROJECT_ID" || handle_error "Failed to create Google Cloud Service Account."
else
  echo "Google Cloud Service Account '$GCP_SA_NAME' already exists."
fi

# Grant necessary IAM roles to the Service Account
echo "Granting IAM roles to Google Cloud Service Account '$GCP_SA_EMAIL'..."
# Grant Cloud SQL Client role
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:$GCP_SA_EMAIL" \
  --role="roles/cloudsql.client" \
  --project="$GCP_PROJECT_ID" --no-user-output-enabled &> /dev/null

# Add more roles here if your application needs access to other GCP services:
# Example: Pub/Sub Subscriber
# gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
#   --member="serviceAccount:$GCP_SA_EMAIL" \
#   --role="roles/pubsub.subscriber" \
#   --project="$GCP_PROJECT_ID" --no-user-output-enabled &> /dev/null

# Example: BigQuery Data Editor
# gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
#   --member="serviceAccount:$GCP_SA_EMAIL" \
#   --role="roles/bigquery.dataEditor" \
#   --project="$GCP_PROJECT_ID" --no-user-output-enabled &> /dev/null

echo "IAM roles granted (or already existed) for '$GCP_SA_EMAIL'."

# Create a new JSON key for the Service Account
echo "Creating new JSON key for Service Account '$GCP_SA_NAME' in '$GCP_SA_KEY_FILE'..."
gcloud iam service-accounts keys create "$GCP_SA_KEY_FILE" \
  --iam-account="$GCP_SA_EMAIL" \
  --project="$GCP_PROJECT_ID" || handle_error "Failed to create Service Account key."

echo "JSON key created successfully: $GCP_SA_KEY_FILE"

# Create Kubernetes Secret from the JSON key
echo "Creating Kubernetes Secret '$GCP_SECRET_NAME' from '$GCP_SA_KEY_FILE' in namespace '$K8S_NAMESPACE'..."
kubectl create secret generic "$GCP_SECRET_NAME" \
  --from-file=key.json="$GCP_SA_KEY_FILE" \
  --namespace="$K8S_NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f - || handle_error "Failed to create GCP credentials secret."

echo "Kubernetes Secret '$GCP_SECRET_NAME' created successfully."
echo "You can verify it with: kubectl get secret $GCP_SECRET_NAME -n $K8S_NAMESPACE -o yaml"
echo ""
echo "IMPORTANT: Remember to update your Kubernetes Deployment YAMLs (e.g., post-ingestion-service.yaml)"
echo "to use the 'google-application-credentials' secret for mounting the key at '/var/secrets/google/key.json'."
echo "Also, ensure the 'cloudsql-proxy' args specify your Cloud SQL instance connection name:"
echo "  -instances=<YOUR_GCP_PROJECT_ID>:<YOUR_GCP_REGION>:<YOUR_POSTGRES_INSTANCE_NAME>=tcp:5432"
