#!/bin/bash

# This script automates the creation/update of Kubernetes Secrets from a .env.development file.

# --- Configuration ---
ENV_FILE="./.env.development" # Path to your .env.development file
NAMESPACE="bluesky-muted-words-plus" # Your target Kubernetes namespace
SECRET_NAME="postgres-credentials" # Name of the Kubernetes Secret

# --- Check for .env file existence ---
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: .env.development file not found at $ENV_FILE"
  echo "Please ensure the file exists and the path is correct."
  exit 1
fi

# --- Ensure the Kubernetes namespace exists ---
echo "Ensuring Kubernetes namespace '$NAMESPACE' exists..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# --- Delete existing secret (optional, but ensures a clean slate) ---
# This helps in case the secret was created with different keys or in a different way before.
echo "Deleting existing secret '$SECRET_NAME' in namespace '$NAMESPACE' (if it exists)..."
kubectl delete secret "$SECRET_NAME" --ignore-not-found -n "$NAMESPACE"

# --- Extract variables from .env.development ---
# Using awk to safely extract values based on the key.
# This avoids issues with values containing spaces or special characters if not quoted properly,
# and minimizes exposing sensitive data.
echo "Extracting variables from $ENV_FILE..."

POSTGRES_USER_VAL=$(awk -F'=' '/^POSTGRES_USER=/{print $2}' "$ENV_FILE")
POSTGRES_DB_VAL=$(awk -F'=' '/^POSTGRES_DB=/{print $2}' "$ENV_FILE")
POSTGRES_PASSWORD_VAL=$(awk -F'=' '/^POSTGRES_PASSWORD=/{print $2}' "$ENV_FILE")
BSKY_HANDLE_VAL=$(awk -F'=' '/^HANDLE=/{print $2}' "$ENV_FILE")
# Note: 'PASSWORD' in your .env maps to 'BSKY_APP_PASSWORD' for clarity in K8s Secret
BSKY_APP_PASSWORD_VAL=$(awk -F'=' '/^PASSWORD=/{print $2}' "$ENV_FILE")

# --- Basic Validation of extracted values ---
if [ -z "$POSTGRES_USER_VAL" ]; then echo "Error: POSTGRES_USER not found or empty in $ENV_FILE"; exit 1; fi
if [ -z "$POSTGRES_DB_VAL" ]; then echo "Error: POSTGRES_DB not found or empty in $ENV_FILE"; exit 1; fi
if [ -z "$POSTGRES_PASSWORD_VAL" ]; then echo "Error: POSTGRES_PASSWORD not found or empty in $ENV_FILE"; exit 1; fi
if [ -z "$BSKY_HANDLE_VAL" ]; then echo "Error: HANDLE not found or empty in $ENV_FILE"; exit 1; fi
if [ -z "$BSKY_APP_PASSWORD_VAL" ]; then echo "Error: PASSWORD (for Bsky app) not found or empty in $ENV_FILE"; exit 1; fi

# --- Create the Kubernetes Secret ---
echo "Creating/updating Kubernetes Secret '$SECRET_NAME' in namespace '$NAMESPACE'..."
kubectl create secret generic "$SECRET_NAME" \
  --from-literal=username="$POSTGRES_USER_VAL" \
  --from-literal=password="$POSTGRES_PASSWORD_VAL" \
  --from-literal=database="$POSTGRES_DB_VAL" \
  --from-literal=handle="$BSKY_HANDLE_VAL" \
  --from-literal=bsky_password="$BSKY_APP_PASSWORD_VAL" \
  --namespace="$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Kubernetes Secret '$SECRET_NAME' created/updated successfully."
echo "You can verify it with: kubectl get secret $SECRET_NAME -n $NAMESPACE -o yaml"
