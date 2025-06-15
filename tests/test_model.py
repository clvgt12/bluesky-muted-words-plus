#!/usr/bin/env python3
#
# test_model.py
#
import argparse
import json
import subprocess
import numpy as np
import requests
from pprint import pprint
from urllib.parse import urlparse
from atproto import Client
from datetime import datetime, timezone
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from server.config import BSKY_USERNAME, BSKY_PASSWORD, MODEL_NAME
from server.logger import setup_logger
from server.text_utils import clean_text, extract_extra_text
from server.vector import string_to_vector, score_post

logger = setup_logger(__name__)

# Load our embedding model once
model = SentenceTransformer(MODEL_NAME)

# Obtain git hash of current commit under test
def get_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    except Exception:
        return "unknown"

# Extract post text from a Bluesky URL
def extract_bluesky_post_text(post_url: str) -> str:
    client = Client()
    client.login(BSKY_USERNAME, BSKY_PASSWORD)

    parsed = urlparse(post_url)
    segments = parsed.path.strip("/").split("/")
    if len(segments) != 4 or segments[0] != "profile" or segments[2] != "post":
        raise ValueError(
            "Unsupported URL format. Expected: https://bsky.app/profile/{handle}/post/{post_id}"
        )

    handle = segments[1]
    post_id = segments[3]
    did = client.com.atproto.identity.resolve_handle({"handle": handle})["did"]
    at_uri = f"at://{did}/app.bsky.feed.post/{post_id}"

    posts = client.app.bsky.feed.get_posts({"uris": [at_uri]})
    if not posts["posts"]:
        raise ValueError(f"No post found for URI: {at_uri}")

    post_record = posts["posts"][0]["record"]
    try:
        record_dict = (
            post_record.model_dump()
            if hasattr(post_record, "model_dump")
            else post_record
        )
        print("\n=== Raw EMBED Dump ===")
        pprint(record_dict.get("embed", {}), indent=2, width=120, sort_dicts=False)
        print("======================\n")
    except Exception as e:
        print("Failed to dump embed:", e)

    main_text = post_record.text
    extra_text = extract_extra_text(post_record)
    combined = f"{main_text} {extra_text}"
    logger.info(f"Combined text: {combined}")
    return clean_text(combined)

# Fetch and clean text from a URL
def fetch_url_text(url: str) -> str:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return clean_text(resp.text)
    except Exception as e:
        logger.error(f"Failed to fetch URL {url}: {e}")
        return ""

# Build a single averaged vector from a list of "documents"
def average_vectors(docs: list[str]) -> np.ndarray:
    if not docs:
        return np.zeros(model.get_sentence_embedding_dimension())
    vecs = [string_to_vector(doc) for doc in docs]
    return np.mean(vecs, axis=0)

# ---- Main test function ----
def run_test(
    post_url: str,
    test_description: str,
    expected_classification: str,
    lists_path: str
):
    print(f"🔍 {test_description}")
    print(f"🔗 {post_url}")

    cleaned = extract_bluesky_post_text(post_url)
    print(f"\n🧹 Cleaned Text:\n{cleaned}\n")

    # Load user lists JSON (nested under "white_list" / "black_list")
    with open(lists_path, 'r') as f:
        cfg = json.load(f)

    wl = cfg.get("white_list", {})
    white_words = wl.get("words", [])
    white_urls = wl.get("urls", [])

    bl = cfg.get("black_list", {})
    black_words = bl.get("words", [])
    black_urls = bl.get("urls", [])

    # Build docs
    white_docs = [" ".join(white_words)] + [fetch_url_text(u) for u in white_urls]
    black_docs = [" ".join(black_words)] + [fetch_url_text(u) for u in black_urls]

    # Vectorize & average
    white_list_vector = average_vectors(white_docs)
    black_list_vector = average_vectors(black_docs)

    # Score post
    post_vector = string_to_vector(cleaned)
    result = score_post(
        post_vector,
        white_list_vector,
        black_list_vector,
        post_text=cleaned,
        whitelist_words=white_words,
        blacklist_words=black_words,
    )

    expected = expected_classification.upper()
    observed = result["decision"]
    passed = expected == observed

    output = {
        "test_description": test_description,
        "url": post_url,
        "timestamp_utc": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        "git_commit": get_git_commit(),
        "model_params": {
            "show_threshold": result.get("show_threshold"),
            "hide_threshold": result.get("hide_threshold"),
            "softmax_temperature": result.get("temperature"),
            "bias_weight": result.get("bias_weight"),
        },
        "cosine_similarity_results": {
            "whitelist": round(result["raw_white"], 4),
            "blacklist": round(result["raw_black"], 4),
        },
        "softmax_probability_scores": {
            "whitelist": round(result["prob_white"], 4),
            "blacklist": round(result["prob_black"], 4),
        },
        "expected_classification": expected,
        "observed_classification": observed,
        "result": "PASS" if passed else "FAIL",
    }

    print(json.dumps(output, indent=2))
    return output

# ---- CLI entrypoint ----
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Run a test against Bluesky post classifier"
    )
    parser.add_argument(
        "-u", "--url", required=True,
        help="Bluesky post URL"
    )
    parser.add_argument(
        "-d", "--test_description", required=True,
        help="Test description"
    )
    parser.add_argument(
        "-c", "--classification", required=True,
        choices=["SHOW", "HIDE", "AMBIGUOUS"],
        help="Expected classification"
    )
    parser.add_argument(
        "-l", "--lists",
        default="./data/user_list.json",
        help=(
            "Path to JSON file with nested keys: white_list.words, "
            "white_list.urls, black_list.words, black_list.urls"
        )
    )
    args = parser.parse_args()

    run_test(
        args.url,
        args.test_description,
        args.classification,
        args.lists,
    )
