#!/usr/bin/env python3
#
# test_driver.py
#
import argparse
import json
import subprocess
import sys
import numpy as np
from pprint import pprint
from urllib.parse import urlparse
from atproto import Client
from datetime import datetime, timezone
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from server.config import BSKY_USERNAME, BSKY_PASSWORD, DEFAULT_DID
from server.logger import setup_logger
from server.text_utils import clean_text, extract_extra_text
from server.vector import string_to_vector, vector_to_blob, cosine_similarity, score_post, model
from server.database import db, Post, PostVector, UserLists


logger = setup_logger(__name__)

# Obtain git hash of current commit under test
def get_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    except Exception:
        return "unknown"

# Extract post text from a Bluesky URL ----
def extract_bluesky_post_text(post_url: str) -> str:
    client = Client()
    client.login(BSKY_USERNAME, BSKY_PASSWORD)

    parsed = urlparse(post_url)
    segments = parsed.path.strip("/").split("/")
    if len(segments) != 4 or segments[0] != "profile" or segments[2] != "post":
        raise ValueError("Unsupported URL format. Expected: https://bsky.app/profile/{handle}/post/{post_id}")

    handle = segments[1]
    post_id = segments[3]
    did = client.com.atproto.identity.resolve_handle({"handle": handle})["did"]
    at_uri = f"at://{did}/app.bsky.feed.post/{post_id}"

    posts = client.app.bsky.feed.get_posts({"uris": [at_uri]})
    if not posts["posts"]:
        raise ValueError(f"No post found for URI: {at_uri}")

    post_record = posts["posts"][0]["record"]
    try:
        record_dict = post_record.model_dump() if hasattr(post_record, "model_dump") else post_record
        print("\n=== Raw EMBED Dump ===")
        pprint(record_dict.get("embed", {}), indent=2, width=120, sort_dicts=False)
        print("======================\n")
    except Exception as e:
        print("Failed to dump embed:", e)

    main_text = post_record.text
    extra_text = extract_extra_text(post_record)
    text = f"{main_text} {extra_text}"
    logger.info(f"Combined main and extra text: {text}")
    return clean_text(text)

# ---- Store post in DB and vectorize ----
def store_post(uri: str, cid: str, cleaned_text: str) -> Post:
    post = Post.create(uri=uri, cid=cid)
    vector = string_to_vector(cleaned_text, model)
    PostVector.create(
        post=post,
        post_text=cleaned_text,
        post_vector=vector_to_blob(vector),
        post_dim=len(vector)
    )
    return post

# ---- Retrieve user whitelist and blacklist vectors ----
def fetch_user_vectors(did: str) -> tuple[np.ndarray, np.ndarray, UserLists]:
    row = UserLists.get_or_none(UserLists.did == DEFAULT_DID)
    if not row:
        print(f"No UserLists entry for DID: {DEFAULT_DID}")
        sys.exit(1)
    white_vec = np.frombuffer(row.white_list_vector, dtype=np.float32, count=row.white_list_dim)
    black_vec = np.frombuffer(row.black_list_vector, dtype=np.float32, count=row.black_list_dim)
    return white_vec, black_vec, row

# ---- Main test function ----
def run_test(post_url: str, test_description: str, expected_classification: str):
    print(f"🔍 {test_description}")
    print(f"🔗 {post_url}")

    cleaned = extract_bluesky_post_text(post_url)
    print(f"\n🧹 Cleaned Text:\n{cleaned}\n")

    post = store_post(uri=post_url, cid="dummy-cid", cleaned_text=cleaned)

    whitelist_vec, blacklist_vec, row = fetch_user_vectors(DEFAULT_DID)
    post_vector = post.vector.get()
    post_vec = np.frombuffer(post_vector.post_vector, dtype=np.float32, count=post_vector.post_dim)

    result = score_post(
        post_vec,
        whitelist_vec,
        blacklist_vec,
        post_text=cleaned,
        whitelist_words=row.white_list_text.split(),
        blacklist_words=row.black_list_text.split()
    )

    expected = expected_classification.upper()
    observed = result["decision"]
    passed = expected == observed

    output = {
        "test_description": test_description,
        "url": post_url,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": get_git_commit(),
        "model_params": {
            "show_threshold": result.get("show_threshold", None),
            "hide_threshold": result.get("hide_threshold", None),
            "softmax_temperature": result.get("temperature", None),
            "bias_weight": result.get("bias_weight", None)
        },
        "cosine_similarity_results": {
            "whitelist": round(result["raw_white"], 4),
            "blacklist": round(result["raw_black"], 4)
        },
        "softmax_probability_scores": {
            "whitelist": round(result["prob_white"], 4),
            "blacklist": round(result["prob_black"], 4)
        },
        "expected_classification": expected,
        "observed_classification": observed,
        "result": "PASS" if passed else "FAIL"
    }

    print(json.dumps(output, indent=2))
    return output

# ---- CLI entrypoint ----
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a test against Bluesky post classifier")
    parser.add_argument("-u", "--url", required=True, help="Bluesky post URL")
    parser.add_argument("-d", "--test_description", required=True, help="Test description")
    parser.add_argument("-c", "--classification", required=True, help="Expected classification (SHOW, HIDE, AMBIGUOUS)")
    args = parser.parse_args()

    run_test(args.url, args.test_description, args.classification)
