#!/usr/bin/env python3
# user_list_tool.py

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import List

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from server.config import DEFAULT_DID
from server.database import UserLists, db
from server.text_utils import clean_text, get_webpage_text
from server.vector import string_to_vector, vector_to_blob, model

def fetch_vectors_from_urls(urls: List[str]) -> List:
    vectors = []
    for url in urls:
        print(f"Processing {url}...")
        try:
            raw = get_webpage_text(url)
            if not raw or len(raw.strip()) < 100:
                print(f"⚠️ Skipped {url}: content was empty or too short")
                continue
            cleaned = clean_text(raw)
            vec = string_to_vector(cleaned, model)
            vectors.append(vec)
        except Exception as e:
            print(f"❌ Skipped {url}: {type(e).__name__} — {e}")
    return vectors

def upsert_from_json(did: str, json_path: str) -> None:
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found: '{json_path}'")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Failed to parse JSON: {e}")
        sys.exit(1)

    for kind in ("white_list", "black_list"):
        print(f"Processing {kind.replace("_"," ")}")
        section = data.get(kind, {})
        words = section.get("words", [])
        urls = section.get("urls", [])

        vectors = []

        if words:
            keyword_text = " ".join(words)
            print(f"Processing keywords...")
            vectors.append(string_to_vector(keyword_text, model))
        else:
            keyword_text = ""

        vectors += fetch_vectors_from_urls(urls)

        if not vectors:
            print(f"\u26a0\ufe0f No valid vectors for {kind}; skipping.")
            continue

        combined_vec = sum(vectors) / len(vectors)
        blob = vector_to_blob(combined_vec)
        dim = combined_vec.shape[0]
        now = datetime.now(timezone.utc)

        # Determine DB fields
        vector_field = f"{kind}_vector"
        text_field = f"{kind}_text"
        dim_field = f"{kind}_dim"
        urls_field = f"{kind}_urls"

        # Perform DB upsert
        try:
            row = UserLists.get(UserLists.did == did)
            update_data = {
                text_field: keyword_text,
                vector_field: blob,
                dim_field: dim,
                urls_field: json.dumps(urls),
                "modified_at": now
            }
            UserLists.update(**update_data).where(UserLists.did == did).execute()
        except UserLists.DoesNotExist:
            insert_data = {
                "did": did,
                text_field: keyword_text,
                vector_field: blob,
                dim_field: dim,
                urls_field: json.dumps(urls),
                "modified_at": now
            }
            UserLists.create(**insert_data)

        print(f"\u2705 Stored {kind.replace('_', ' ').title()} for DID={did}")


def retrieve_lists(did: str):
    try:
        row = UserLists.select().where(UserLists.did == did).get()
        print(f"DID={row.did}")
        print(f"  Whitelist: [ {row.white_list_text.replace(' ', ', ')} ]")
        print(f"  Whitelist URLs: {row.white_list_urls}")
        print(f"  Blacklist: [ {row.black_list_text.replace(' ', ', ')} ]")
        print(f"  Blacklist URLs: {row.black_list_urls}")
        print(f"  Modified:  {row.modified_at.strftime('%Y-%m-%d %H:%M:%S %Z %z')}\n")
    except UserLists.DoesNotExist:
        print(f"No entry found for DID={did}")


def main():
    parser = argparse.ArgumentParser(description="Vectorize and store whitelist/blacklist with example URLs")
    parser.add_argument("-d", "--did", help="Bluesky DID", default=None)
    parser.add_argument("-j", "--json_path", help="Path to structured JSON input", required=False)
    args = parser.parse_args()

    did = args.did or DEFAULT_DID
    if not did:
        print("A BlueSky DID must be specified!")
        sys.exit(1)

    if args.json_path:
        upsert_from_json(did, args.json_path)
    else:
        retrieve_lists(did)


if __name__ == "__main__":
    main()
