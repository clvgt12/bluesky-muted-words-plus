#!/usr/bin/env python3
#
# user_list_tool.py
#
# This is a streamlit application that maintains the users' white- and blacklists
# in the database.  To invoke from the command line:
#
# $ source [Python3 venv path]
# $ cd [git project root directory]
# $ PYTHONPATH=$(pwd) $(which streamlit) run server/user_list_tool.py
# 
import streamlit as st
import json
import os
from datetime import datetime, timezone
from server.config import DEFAULT_DID
from server.database import UserLists, db
from server.vector import blob_to_vector, string_to_vector, vector_to_blob
from server.text_utils import clean_text, get_webpage_text
import numpy as np

DEFAULT_JSON_PATH = "data/user_list.json"

st.set_page_config(page_title="User List Manager", layout="centered")
st.title("📋 User List Editor")

@st.cache_data(show_spinner=False)
def load_user_lists(did):
    try:
        row = UserLists.select().where(UserLists.did == did).get()
        return {
            "white_list": {
                "words": row.white_list_text.split(),
                "urls": json.loads(row.white_list_urls or "[]")
            },
            "black_list": {
                "words": row.black_list_text.split(),
                "urls": json.loads(row.black_list_urls or "[]")
            }
        }
    except UserLists.DoesNotExist:
        return {"white_list": {"words": [], "urls": []}, "black_list": {"words": [], "urls": []}}

def dump_vectors_to_console(did):
    try:
        row = UserLists.select().where(UserLists.did == did).get()
        for kind in ("white_list", "black_list"):
            vec_blob = getattr(row, f"{kind}_vector")
            vec_dim = getattr(row, f"{kind}_dim")
            if vec_blob:
                vec = blob_to_vector(vec_blob, vec_dim)
                print(f"\n=== {kind.replace('_', ' ').title()} Vector ({vec.shape[0]} dims) ===")
                print(", ".join(f"{x:.4f}" for x in vec))
            else:
                print(f"{kind.replace('_', ' ').title()} vector is empty or missing.")
    except UserLists.DoesNotExist:
        print(f"No entry found for DID={did}")

def save_to_database(did, data):
    now = datetime.now(timezone.utc)
    for kind in ("white_list", "black_list"):
        words = data[kind].get("words", [])
        urls = data[kind].get("urls", [])

        vectors = []
        keyword_text = " ".join(words)
        if words:
            vectors.append(string_to_vector(keyword_text))

        for url in urls:
            try:
                raw = get_webpage_text(url)
                if raw and len(raw.strip()) > 100:
                    cleaned = clean_text(raw)
                    vectors.append(string_to_vector(cleaned))
            except Exception:
                continue

        if not vectors:
            continue

        combined_vec = sum(vectors) / len(vectors)
        blob = vector_to_blob(combined_vec)
        dim = combined_vec.shape[0]

        try:
            row = UserLists.get(UserLists.did == did)
            update_data = {
                f"{kind}_text": keyword_text,
                f"{kind}_vector": blob,
                f"{kind}_dim": dim,
                f"{kind}_urls": json.dumps(urls),
                "modified_at": now
            }
            UserLists.update(**update_data).where(UserLists.did == did).execute()
        except UserLists.DoesNotExist:
            insert_data = {
                "did": did,
                f"{kind}_text": keyword_text,
                f"{kind}_vector": blob,
                f"{kind}_dim": dim,
                f"{kind}_urls": json.dumps(urls),
                "modified_at": now
            }
            UserLists.create(**insert_data)

@st.cache_data(show_spinner=False)
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

st.sidebar.header("⚙️ Settings")
did = st.sidebar.text_input("DID", value=DEFAULT_DID)
json_path = st.sidebar.text_input("JSON Path", value=DEFAULT_JSON_PATH)

if st.sidebar.button("📂 Load from JSON"):
    file_data = load_json(json_path)
    if file_data:
        st.session_state["lists"] = file_data
        st.success("Loaded JSON file successfully.")
    else:
        st.warning("File not found or invalid JSON.")

if "lists" not in st.session_state:
    st.session_state["lists"] = load_user_lists(did)

lists = st.session_state["lists"]

for kind in ("white_list", "black_list"):
    with st.expander(f"✏️ Edit {kind.replace('_', ' ').title()}", expanded=True):
        word_str = st.text_area(f"Comma-separated {kind} words:", 
                                value=", ".join(lists[kind]["words"]))
        url_list = st.text_area(f"{kind} URLs (one per line):", 
                                value="\n".join(lists[kind]["urls"]))

        lists[kind]["words"] = [w.strip() for w in word_str.split(",") if w.strip()]
        lists[kind]["urls"] = [u.strip() for u in url_list.strip().splitlines() if u.strip()]

col1, col2, col3 = st.columns(3)
if col1.button("💾 Save to Database"):
    save_to_database(did, lists)
    st.success("Saved to database.")

if col2.button("📤 Export to JSON"):
    save_json(json_path, lists)
    st.success(f"Exported to {json_path}")

if col3.button("🧬 Dump Vectors to Console"):
    dump_vectors_to_console(did)
    st.success("Vector data printed to terminal.")
