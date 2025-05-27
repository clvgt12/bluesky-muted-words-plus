#
# test_driver.py
#
import logging
import os
import sys
import numpy as np
from pprint import pprint
from urllib.parse import urlparse
from atproto import Client  # install with: pip install atproto
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from server.logger import logger
from server.text_utils import clean_text, extract_extra_text
from server.vector import string_to_vector, vector_to_blob, cosine_similarity, score_post, model
from server.database import db, Post, PostVector, UserLists

# ---- Config ----
load_dotenv()
model_name = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
DID = os.getenv("DEFAULT_DID", "did:example:1234")
BSKY_USERNAME = os.getenv("HANDLE","vitalos.us")
BSKY_PASSWORD = os.getenv("PASSWORD")
SENSITIVITY = 0.80

# ---- Step 1: Extract post text from a Bluesky URL ----
def extract_bluesky_post_text(post_url: str) -> str:
    client = Client()
    client.login(BSKY_USERNAME, BSKY_PASSWORD)

    parsed = urlparse(post_url)
    segments = parsed.path.strip("/").split("/")
    if len(segments) != 4 or segments[0] != "profile" or segments[2] != "post":
        raise ValueError("Unsupported URL format. Expected format: https://bsky.app/profile/{handle}/post/{post_id}")

    handle = segments[1]
    post_id = segments[3]

    # 🔧 Convert handle to DID
    did = client.com.atproto.identity.resolve_handle({"handle": handle})["did"]
    at_uri = f"at://{did}/app.bsky.feed.post/{post_id}"

    posts = client.app.bsky.feed.get_posts({"uris": [at_uri]})
    if not posts["posts"]:
        raise ValueError(f"No post found for URI: {at_uri}")

    post_record = posts["posts"][0]["record"]
    # Pretty-print the raw embed block
    try:
        record_dict = post_record.model_dump() if hasattr(post_record, "model_dump") else post_record
        print("\n=== Raw EMBED Dump ===")
        pprint(record_dict.get("embed", {}), indent=2, width=120, sort_dicts=False)
        print("======================\n")
    except Exception as e:
        print("Failed to dump embed:", e)
    main_text = post_record.text  # ✅ direct access
    extra_text = extract_extra_text(post_record)  # works with Pydantic or dict
    combined = clean_text(f"{main_text} {extra_text}")

    return combined

# ---- Step 2: Insert post into DB ----
def store_post(uri: str, cid: str, cleaned_text: str) -> Post:
    # model = SentenceTransformer(model_name)
    post = Post.create(uri=uri, cid=cid)
    vector = string_to_vector(cleaned_text, model)
    PostVector.create(
        post=post,
        post_text=cleaned_text,
        post_vector=vector_to_blob(vector),
        post_dim=len(vector)
    )
    return post

# ---- Step 3: Retrieve whitelist & blacklist vectors ----
def fetch_user_vectors(did: str) -> tuple[np.ndarray, np.ndarray, UserLists]:
    row = UserLists.get_or_none(UserLists.did == DID)
    if not row:
        print(f"No UserLists entry for DID: {DID}")
        sys.exit(1)
    white_vec = np.frombuffer(row.white_list_vector, dtype=np.float32, count=row.white_list_dim)
    black_vec = np.frombuffer(row.black_list_vector, dtype=np.float32, count=row.black_list_dim)
    return white_vec, black_vec, row

# ---- Main driver logic ----
def run_test(post_url: str):
    print(f"Fetching and analyzing: {post_url}")
    cleaned = extract_bluesky_post_text(post_url)
    print(f"Cleaned Text: {cleaned}\n")

    post = store_post(uri=post_url, cid="dummy-cid", cleaned_text=cleaned)

    whitelist_vec, blacklist_vec, row = fetch_user_vectors(DID)
    post_vector = post.vector.get()
    post_vec = np.frombuffer(post_vector.post_vector, dtype=np.float32, count=post_vector.post_dim)

    score_white = cosine_similarity(post_vec, whitelist_vec)
    score_black = cosine_similarity(post_vec, blacklist_vec)

    row = UserLists.get(UserLists.did == DID)

    result = score_post(
        post_vec,
        whitelist_vec,
        blacklist_vec,
        post_text=cleaned,
        whitelist_words=row.white_list_text.split(),
        blacklist_words=row.black_list_text.split()
    )

    print(f"Raw cosine (whitelist): {result['raw_white']:.3f}")
    print(f"Raw cosine (blacklist): {result['raw_black']:.3f}")
    print(f"Softmax P(whitelist):   {result['prob_white']:.3f}")
    print(f"Softmax P(blacklist):   {result['prob_black']:.3f}")
    print(f"→ Classification:       {result['decision']}")


# ---- Entry point ----
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_driver.py <bluesky_post_url>")
        sys.exit(1)
    run_test(sys.argv[1])
