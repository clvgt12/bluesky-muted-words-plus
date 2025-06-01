#!/bin/bash

# initialize counters
test_number=0
pass=0
fail=0

function run_driver() {
    local url="$1"
    local desc="$2"
    local result="$3"
    
    ((test_number++))
    echo $(printf "Running test number %d:" "$test_number")
    local output=$(python3 -m tests.test_driver --url="$url" --test_description="$desc" --classification="$result" 2>/dev/null)

    if echo "$output" | grep -q '"result": "PASS"'; then
        ((pass++))
        echo "$output" | awk '/^{$/,/^}$/ {print}'
    elif echo "$output" | grep -q '"result": "FAIL"'; then
        ((fail++))
        echo "$output" | awk '/^{$/,/^}$/ {print}'
    else
        echo "******* ERROR processing test! *******"
    fi
}

echo "=== Running Regression Test Suite ==="

run_driver \
    "https://bsky.app/profile/jamalgreene.bsky.social/post/3lqkv5h2xl22o" \
    "extract only Bluesky post with no white- or blacklist content" \
    "AMBIGUOUS"
run_driver \
    "https://bsky.app/profile/vitalos.us/post/3lq4mkgq3uk2i" \
    "alt_text vs. strong whitelist match" \
    "SHOW"
run_driver \
    "https://bsky.app/profile/vitalos.us/post/3lq4legokhs2i" \
    "alt_text vs. strong blacklist match" \
    "HIDE"
run_driver \
    "https://bsky.app/profile/vitalos.us/post/3ks5y26n6o42k" \
    "extract web page text using personal blog post, compare vs strong whitelist match" \
    "SHOW"
run_driver \
    "https://bsky.app/profile/vitalos.us/post/3lq6sqecbek27" \
    "extract web page text using reddit post, compare vs. strong whitelist match" \
    "SHOW"

echo "=== All Tests Executed ==="
echo "=== Test Summary ==="
echo "Passed: $pass"
echo "Failed: $fail"
