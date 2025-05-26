#!/usr/bin/env python3
# user_list_tool.py

import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from database import UserLists, db
from text_utils import clean_text
from vector import string_to_vector, vector_to_blob

load_dotenv()
model_name = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
default_did = os.getenv("DEFAULT_DID")

# --- CSV reader & vectorizer ---
def read_csv(path: str) -> str:
    """Read a CSV where each row is comma-separated words."""
    words: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            for w in row:
                w = w.strip().lower()
                if w:
                    words.append(w)
    return " ".join(words)

# --- Upsert white and blacklists ---
from datetime import datetime, timezone

def upsert_lists(did: str, args: argparse.Namespace) -> None:
    """
    Slogan: Upsert the whitelist and blacklist (if provided) in one concise loop.
    """
    model = SentenceTransformer(model_name)

    for kind in ("white_list", "black_list"):
        path = getattr(args, kind)
        if not path:
            continue

        # 1) Read & vectorize
        text = read_csv(path)
        vec_arr = string_to_vector(text, model)      # numpy.ndarray
        blob    = vector_to_blob(vec_arr)            # bytes
        dim     = vec_arr.shape[0]

        # 2) Build a dict of the columns we want to update
        update_data = {
            f"{kind}_text":   text,
            f"{kind}_vector": blob,
            f"{kind}_dim":    dim,
            "modified_at":    datetime.now(timezone.utc),
        }

        # 3) Fire the update
        (
            UserLists
            .update(**update_data)
            .where(UserLists.did == did)
            .execute()
        )

        # 4) Friendly feedback
        label = kind.replace("_", " ").title()
        print(f"✅ Stored {label} for DID={did}")
        print(f"   {label}: [ {text.replace(' ', ', ')} ]\n")

# --- Retrieve stored lists ---
def retrieve_lists(did: str):
    """
    Slogan: Retrieve white and blacklists from database.
    """
    try:
        row = UserLists.select().where(UserLists.did == did).get()
        print(f"DID={row.did}")
        print(f"  Whitelist: [ {row.white_list_text.replace(' ',', ')} ]\n")
        print(f"  Blacklist: [ {row.black_list_text.replace(' ',', ')} ]\n")
        print(f"  Modified:  {datetime.fromisoformat(row.modified_at).strftime('%Y-%m-%d %H:%M:%S %Z %z')}\n")
    except UserLists.DoesNotExist:
        print(f"No entry found for DID={did}")

# --- Main CLI logic ---
def main():
    parser = argparse.ArgumentParser(
        description="Vectorize and store whitelist/blacklist word lists"
    )
    parser.add_argument(
        "-d", "--did",
        help="Bluesky DID (e.g. did:plc:...); defaults to $DEFAULT_DID",
        default=None
    )
    parser.add_argument(
        "-w", "--white_list",
        help="Path to whitelist CSV",
        required=False
    )
    parser.add_argument(
        "-b", "--black_list",
        help="Path to blacklist CSV",
        required=False
    )
    args = parser.parse_args()

    did = args.did or default_did
    if did is None:
        print("A BlueSky DID must be specified!")
        sys.exit(1)

    if args.white_list is not None or args.black_list is not None:
        upsert_lists(did, args)
    else:
        retrieve_lists(did)

if __name__ == "__main__":
    main()
