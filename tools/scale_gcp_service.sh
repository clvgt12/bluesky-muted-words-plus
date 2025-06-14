#!/bin/bash
set -euo pipefail

SERVICE="bluesky-muted-words-plus"
REGION="us-east1"
PLATFORM="managed"

function usage() {
  echo "Usage: $0 [-h] <scale_target>"
  echo ""
  echo "Options:"
  echo "  -h, --help           Show this help message and exit"
  echo ""
  echo "Positional Arguments:"
  echo "  <scale_target>       Number of minimum instances (e.g., 0 to scale to zero)"
  echo ""
  echo "Examples:"
  echo "  $0 0       # scale to zero"
  echo "  $0 2       # scale up to 2 instances"
  exit 0
}

# Parse options
while getopts ":h-:" opt; do
  case "$opt" in
    h) usage ;;
    -)
      case "${OPTARG}" in
        help) usage ;;
        *) echo "❌ Unknown option --${OPTARG}" >&2; usage ;;
      esac ;;
    *) echo "❌ Unknown option -${OPTARG}" >&2; usage ;;
  esac
done
shift $((OPTIND - 1))

# Expecting one positional argument
if [[ $# -ne 1 ]]; then
  echo "❌ Error: You must provide a <scale_target> value."
  usage
fi

SCALE_TARGET="$1"

# Validate input is non-negative integer
if ! [[ "$SCALE_TARGET" =~ ^[0-9]+$ ]]; then
  echo "❌ Error: <scale_target> must be a non-negative integer."
  usage
fi

echo "🔧 Updating service '$SERVICE' to scale to $SCALE_TARGET instance(s)..."

gcloud run services update "$SERVICE" \
    --region="$REGION" \
    --platform="$PLATFORM" \
    --cpu=2 \
    --memory="4Gi" \
    --min-instances="$SCALE_TARGET"

echo "✅ Service '$SERVICE' updated to min-instances=$SCALE_TARGET"