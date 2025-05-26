# vector.py
# Vector operations using NumPy

import os
import numpy as np
from typing import List
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()
model_name = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
model = SentenceTransformer(model_name)

def words_to_vector(words: List[str], model: SentenceTransformer) -> np.ndarray:
    """
    Join a list of words and encode to a NumPy float32 vector.
    """
    text = " ".join(words)
    return model.encode(text).astype(np.float32)

def string_to_vector(string: str, model: SentenceTransformer) -> np.ndarray:
    """
    Encode a string to a NumPy float32 vector.
    """
    return model.encode(string).astype(np.float32)

def vector_to_blob(vec: np.ndarray) -> bytes:
    """
    Convert a Numpy array into a binary blob for database storage
    """
    return vec.astype(np.float32).tobytes()

def blob_to_vector(blob: bytes, dim: int) -> np.ndarray:
    """
    Convert a Numpy array into a binary blob for database retrieval
    """
    return np.frombuffer(blob, dtype=np.float32, count=dim)

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two NumPy vectors.
    Returns a float in the range [-1.0, 1.0].
    """
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))

def score_post(post: np.ndarray, whitelist: np.ndarray, blacklist: np.ndarray, sensitivity: float) -> bool:
    """
    Compare a post vector to whitelist and blacklist vectors using cosine similarity.
    Returns True if the average score exceeds or meets the sensitivity threshold.
    """
    r1 = cosine_similarity(post, whitelist)
    r2 = 1.0 - cosine_similarity(post, blacklist)
    avg = (r1 + r2) / 2.0
    return avg >= sensitivity
