#!/bin/bash
set -euo pipefail

# --- Configuration ---
IMAGE_NAME="bluesky-muted-words-plus"
TAG="latest"
REPO_NAME="$IMAGE_NAME"

# --- Detect AWS Account ID and Region ---
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

if [[ -z "$AWS_ACCOUNT_ID" || -z "$AWS_REGION" ]]; then
  echo "❌ Failed to detect AWS credentials or region. Run 'aws configure' first."
  exit 1
fi

# --- Construct ECR URI ---
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:${TAG}"

echo "🔍 AWS Account ID: $AWS_ACCOUNT_ID"
echo "🌍 AWS Region: $AWS_REGION"
echo "📦 ECR Target: $ECR_URI"

# --- Create the ECR repository if it doesn't exist ---
if ! aws ecr describe-repositories --repository-names "$REPO_NAME" >/dev/null 2>&1; then
  echo "📁 ECR repository '$REPO_NAME' not found. Creating..."
  aws ecr create-repository --repository-name "$REPO_NAME"
else
  echo "✅ ECR repository '$REPO_NAME' already exists."
fi

# --- Authenticate Docker with ECR ---
echo "🔐 Logging in to ECR..."
aws ecr get-login-password \
  | docker login --username AWS \
    --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# --- Check if image exists locally ---
if docker image inspect "${IMAGE_NAME}:${TAG}" > /dev/null 2>&1; then
  echo "✅ Local image '${IMAGE_NAME}:${TAG}' found. Skipping build."
else
  echo "🔧 Local image '${IMAGE_NAME}:${TAG}' not found. Building image..."
  docker build -t "${IMAGE_NAME}:${TAG}" .
fi

# --- Tag the image for ECR ---
echo "🏷️ Tagging image as $ECR_URI"
docker tag "${IMAGE_NAME}:${TAG}" "$ECR_URI"

# --- Push the image to ECR ---
echo "🚀 Pushing image to AWS ECR..."
docker push "$ECR_URI"

# --- Output final image URI ---
echo ""
echo "✅ Docker image successfully pushed to:"
echo "   $ECR_URI"
echo ""
echo "➡️ Use this URI when deploying via AWS App Runner or ECS."
