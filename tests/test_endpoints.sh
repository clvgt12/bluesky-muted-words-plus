#!/bin/bash
#
# Test endpoints with pagination and optional duplicate URI detection
#

# Load .env.development if it exists
if [[ -f .env.development ]]; then
  export $(grep -v '^#' .env.development | xargs)
fi

# Adapted for minikube environment

HOST_IP=$(kubectl get service feed-endpoint-service -n bluesky-muted-words-plus -o jsonpath='{.spec.clusterIP}')
DEFAULT_DID="${DEFAULT_DID:-did:plc:btd7cocvy4na2wyowrpbo64o}"
AUTH_HEADER="Authorization: Bearer dev:$DEFAULT_DID"
BASE_URL="http://$HOST_IP:80"
ENDPOINTS=("/" "/health/" "/test-feed-handler/?limit=20")

for endpoint in "${ENDPOINTS[@]}"; do
  echo "🔎 Testing endpoint: $endpoint"

  if [[ "$endpoint" == *"/test-feed-handler/"* ]]; then
    response=$(curl -s -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL$endpoint")
  else
    response=$(curl -s -w "%{http_code}" "$BASE_URL$endpoint")
  fi

  body="${response::-3}"
  status="${response: -3}"

  if [[ "$status" == "200" ]]; then
    echo "  ✅ Status: 200 OK"
  else
    echo "  ❌ Status: $status"
    echo "  ↪ Response body: $body"
    continue
  fi

  echo "$body" | jq . >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "  ✅ JSON: Valid"
  else
    echo "  ❌ JSON: Invalid"
    echo "  ↪ Body: $body"
  fi

  # Optional: Handle pagination if `cursor` is present
  if [[ "$endpoint" == *"/test-feed-handler/"* ]]; then
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
      paged_response=$(curl -s -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/test-feed-handler/?cursor=$cursor&limit=20")
      paged_body="${paged_response::-3}"
      paged_status="${paged_response: -3}"

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
