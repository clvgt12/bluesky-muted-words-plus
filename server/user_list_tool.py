#!/usr/bin/env python3
# user_lists.py
import argparse
import csv
import json
import os
import sys
from datetime import datetime

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from database import UserLists, db

load_dotenv()
model_name = os.getenv("MODEL_NAME","sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
default_did = os.getenv("DEFAULT_DID")

# --- CSV reader & vectorizer ---
def read_csv_words(path: str) -> list[str]:
    """Read a CSV where each row is comma-separated words."""
    words: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            for w in row:
                w = w.strip()
                if w:
                    words.append(w)
    return words

def vectorize_to_list(words: list[str], model: SentenceTransformer) -> list[float]:
    """
    Join words, encode to a NumPy float32 array, then convert to a Python list of floats.
    """
    text = " ".join(words)
    vec  = model.encode(text)                 # numpy.ndarray
    return vec.astype(np.float32).tolist()    # List[float]

# --- Main CLI logic ---
def main():
    parser = argparse.ArgumentParser(
        description="Load white/black lists, vectorize, and store via Peewee (JSON storage)"
    )
    parser.add_argument(
        "-d", "--did",
        help="Bluesky DID (e.g. did:plc:...); defaults to $DEFAULT_DID",
        default=None
    )
    parser.add_argument(
        "-w", "--whitelist",
        help="Path to whitelist CSV",
        required=True
    )
    parser.add_argument(
        "-b", "--blacklist",
        help="Path to blacklist CSV",
        required=True
    )
    args = parser.parse_args()

    # load embedding model once
    model = SentenceTransformer(model_name)

    # determine did
    did = args.did or default_did
    if did is None:
        print("A BlueSky DID must be specified!")
        sys.exit(1)

    # read & vectorize → Python lists
    white_words = read_csv_words(args.whitelist)
    black_words = read_csv_words(args.blacklist)
    white_list  = vectorize_to_list(white_words, model)
    black_list  = vectorize_to_list(black_words, model)

    # insert (or replace) via Peewee, JSON-encoding the lists
    UserLists.replace(
        did=did,
        white_list=json.dumps(white_list),
        black_list=json.dumps(black_list),
        modified_at=datetime.utcnow()
    ).execute()

    print(f"✅ Stored JSON-encoded embeddings for DID={did}")

if __name__ == "__main__":
    main()
