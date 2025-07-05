#!/bin/bash
#
# Test endpoints with pagination and optional duplicate URI detection
#
# This version is updated to test via the Ingress Controller
# using a DNS-resolved hostname (e.g., minikube.lan)
#
# Includes a check to ensure minikube tunnel is running.
# Includes verbose curl output for debugging.

# Load .env.development if it exists
if [[ -f .env.development ]]; then
  export $(grep -v '^#' .env.development | xargs)
fi

# --- MODIFIED FOR INGRESS TESTING ---
# The hostname that your Ingress resource is configured to listen for.
# This MUST match the 'host:' field in your Ingress YAML (e.g., "minikube.lan").
INGRESS_HOST="minikube.lan"

# Explicitly define the port curl should connect to.
# This is the NodePort exposed by minikube tunnel for HTTP traffic.
INGRESS_PORT="30080"

# Get the Minikube IP for --connect-to. This ensures curl connects to the Minikube VM.
# IMPORTANT: Use 'tr -d "\n"' to remove any newline characters from the output of minikube ip.
MINIKUBE_IP=$(minikube ip | tr -d '\n')

FEED_BASE_PATH="/feed"     # Path for the feed-endpoint service in Ingress
ADMIN_BASE_PATH="/admin-portal" # Path for the user-list-tool service in Ingress

# Default DID and Auth Header
DEFAULT_DID="${DEFAULT_DID:-did:plc:btd7cocvy4na2wyowrpbo64o}"
AUTH_HEADER="Authorization: Bearer dev:$DEFAULT_DID"

# Define endpoints relative to their Ingress paths
ENDPOINTS=("$FEED_BASE_PATH/health/" "$FEED_BASE_PATH/test-feed-handler/?limit=20")

# --- Function to check if minikube tunnel is running ---
check_minikube_tunnel() {
  local retries=5
  local delay=5
  echo "⏳ Checking if 'minikube tunnel' is running..."
  for i in $(seq 1 $retries); do
    if pgrep -f "minikube tunnel" > /dev/null; then
      echo "✅ 'minikube tunnel' is running."
      return 0
    else
      echo "Waiting for 'minikube tunnel' to start (attempt $i/$retries)..."
      echo "Please ensure 'minikube tunnel' is running in a separate terminal and has sudo/admin access."
      sleep $delay
    fi
  done
  echo "❌ 'minikube tunnel' is not running. Please start it manually and re-run the script."
  return 1
}

# --- Perform the minikube tunnel check before proceeding ---
if ! check_minikube_tunnel; then
  exit 1
fi

# --- Test Feed Endpoint ---
echo "--- Testing Feed Endpoint via Ingress ---"
for endpoint in "${ENDPOINTS[@]}"; do

  # Construct the full URL for the request. Curl will connect to MINIKUBE_IP:INGRESS_PORT
  # due to --connect-to, but send Host: INGRESS_HOST.
  REQUEST_URL="http://$INGRESS_HOST:$INGRESS_PORT$endpoint"
  echo "🔎 Testing Ingress path: $REQUEST_URL"

  # Use an array for CURL_COMMAND_ARGS to ensure proper argument parsing by curl.
  # This avoids issues with spaces, quotes, and special characters in arguments.
  CURL_COMMAND_ARGS=(
    -s
    -w "%{http_code}"
    --connect-to "$INGRESS_HOST:$INGRESS_PORT:$MINIKUBE_IP" # No internal quotes needed here
    -H "Host: $INGRESS_HOST" # No internal quotes needed here
  )

  # Execute curl command, capturing all output (stdout and stderr)
  if [[ "$endpoint" == *"$FEED_BASE_PATH/test-feed-handler/"* ]]; then
    response_output=$(curl "${CURL_COMMAND_ARGS[@]}" -H "$AUTH_HEADER" "$REQUEST_URL")
  else
    response_output=$(curl "${CURL_COMMAND_ARGS[@]}" "$REQUEST_URL")
  fi

  # Extract status code (last 3 characters)
  status="${response_output: -3}"
  # Extract body and headers (everything before the last 3 characters)
  raw_output_before_status="${response_output%???}"

  # Separate headers from body (verbose output starts with '< ' or '* ')
  headers=$(echo "$raw_output_before_status" | sed -n '/^< /p')
  body=$(echo "$raw_output_before_status" | sed '/^< /d' | sed '/^\* /d')

  if [[ "$status" == "200" ]]; then
    echo "  ✅ Status: 200 OK"
  else
    echo "  ❌ Status: $status"
    echo "  ↪ Response body: $body"
    continue
  fi

  # Now, try to parse the cleaned body with jq
  echo "$body" | jq . >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "  ✅ JSON: Valid"
  else
    echo "  ❌ JSON: Invalid"
    echo "  ↪ Body: $body"
  fi

  # Optional: Handle pagination if `cursor` is present
  if [[ "$endpoint" == *"$FEED_BASE_PATH/test-feed-handler/"* ]]; then
    cursor=$(echo "$body" | jq -r '.cursor')
    post_count=$(echo "$body" | jq '.feed | length')
    echo "  📦 Page 1 Post count: $post_count"

    declare -A seen_uris
    uris=$(echo "$body" | jq -r '.feed[].post')
    for uri in $uris; do
      if [[ -n "${seen_uris[$uri]}" ]]; then
        echo "  ⚠️ Duplicate URI found: $uri"
      fi
      seen_uris[$uri]=1
    done

    page=2
    while [[ "$cursor" != "eof" && "$cursor" != "null" ]]; do
      echo "🔁 Fetching page $page with cursor: $cursor"
      # Use the Ingress hostname and path for subsequent paginated requests
      PAGED_REQUEST_URL="http://$INGRESS_HOST:$INGRESS_PORT$FEED_BASE_PATH/test-feed-handler/?cursor=$cursor&limit=20"
      PAGED_CURL_COMMAND_ARGS=(
        -s
        -w "%{http_code}"
        --connect-to "$INGRESS_HOST:$INGRESS_PORT:$MINIKUBE_IP:$INGRESS_PORT"
        -H "Host: $INGRESS_HOST"
      )
      paged_response_output=$(curl "${PAGED_CURL_COMMAND_ARGS[@]}" -H "$AUTH_HEADER" "$PAGED_REQUEST_URL")
      
      paged_status="${paged_response_output: -3}"
      paged_raw_output_before_status="${paged_response_output%???}"

      paged_headers=$(echo "$paged_raw_output_before_status" | sed -n '/^< /p')
      paged_body=$(echo "$paged_raw_output_before_status" | sed '/^< /d' | sed '/^\* /d')

      if [[ "$paged_status" == "200" ]]; then
        echo "    ✅ Page $page Status: 200 OK"
      else
        echo "    ❌ Page $page Status: $paged_status"
        echo "    ↪ Response: $paged_body"
        break
      fi

      echo "$paged_body" | jq . >/dev/null 2>&1
      if [[ $? -eq 0 ]]; then
        echo "    ✅ Page $page JSON: Valid"
      else
        echo "    ❌ Page $page JSON: Invalid"
        echo "    ↪ Body: $paged_body"
      fi

      post_count=$(echo "$paged_body" | jq '.feed | length')
      echo "    📦 Page $page Post count: $post_count"

      uris=$(echo "$paged_body" | jq -r '.feed[].post')
      for uri in $uris; do
        if [[ -n "${seen_uris[$uri]}" ]]; then
          echo "    ⚠️ Duplicate URI found: $uri"
        fi
        seen_uris[$uri]=1
      done

      cursor=$(echo "$paged_body" | jq -r '.cursor')
      if [[ "$cursor" == "eof" ]]; then
        echo "    🔚 Reached end of feed."
        break
      fi
      ((page++))
    done
    echo ""
  fi
done

# --- Test User List Tool (Admin Portal) - Manual Browser Check ---
echo "--- To test User List Tool (Admin Portal), open this URL in your browser: ---"
echo "http://$INGRESS_HOST:$INGRESS_PORT$ADMIN_BASE_PATH"
echo "-------------------------------------------------------------------"
