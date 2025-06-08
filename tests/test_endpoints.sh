#!/bin/bash
#
# Test endpoints
#
BASE_URL="http://localhost:8000"
ENDPOINTS=("/" "/health/" "/test-feed-handler/")

for endpoint in "${ENDPOINTS[@]}"; do
  echo "Testing endpoint: $endpoint"

  response=$(curl -s -w "%{http_code}" "$BASE_URL$endpoint")
  body="${response::-3}"
  status="${response: -3}"

  if [[ "$status" == "200" ]]; then
    echo "  ✅ Status: 200 OK"
  else
    echo "  ❌ Status: $status"
    continue
  fi

  echo "$body" | jq . >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "  ✅ JSON: Valid"
  else
    echo "  ❌ JSON: Invalid"
  fi
done
