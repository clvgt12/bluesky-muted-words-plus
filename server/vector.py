# vector.py
# Vector operations using NumPy

import logging
import os
import numpy as np
from typing import List, Literal
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from server.logger import logger
from server.text_utils import keyword_match_bias

# Configuration

load_dotenv()
model_name = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
model = SentenceTransformer(model_name)
show_thresh = float(os.getenv("SHOW_THRESHOLD", 0.75))
hide_thresh = float(os.getenv("HIDE_THRESHOLD", 0.75))
temperature = float(os.getenv("SOFTMAX_TEMPERATURE", 1.0))

# Enforce limits
show_thresh = min(max(show_thresh, 0.0), 1.0)
hide_thresh = min(max(hide_thresh, 0.0), 1.0)

# Clamp temperature to safe minimum value
if temperature <= 0.0:
    logger.error("⚠️  SOFTMAX_TEMPERATURE must be > 0. Defaulting to 1.0.")
    temperature = 1.0

def words_to_vector(words: List[str], model: SentenceTransformer) -> np.ndarray:
    text = " ".join(words)
    return model.encode(text).astype(np.float32)

def string_to_vector(string: str, model: SentenceTransformer) -> np.ndarray:
    return model.encode(string).astype(np.float32)

def vector_to_blob(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()

def blob_to_vector(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=dim)

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))

# --- New softmax-based scoring ---
def softmax_similarity_scores(post_vec: np.ndarray,
                              white_vec: np.ndarray,
                              black_vec: np.ndarray,
                              temperature: float = temperature) -> dict:
    s_white = cosine_similarity(post_vec, white_vec)
    s_black = cosine_similarity(post_vec, black_vec)

    logits = np.array([s_white, s_black]) / temperature
    exp_logits = np.exp(logits - np.max(logits))  # stabilize
    probs = exp_logits / exp_logits.sum()

    return {
        "prob_white": float(probs[0]),
        "prob_black": float(probs[1]),
        "raw_white": s_white,
        "raw_black": s_black
    }

def classify_post_softmax(prob_white: float, prob_black: float,
                          show_thresh: float = show_thresh,
                          hide_thresh: float = hide_thresh) -> Literal["SHOW", "HIDE", "AMBIGUOUS"]:
    if prob_white >= show_thresh:
        return "SHOW"
    elif prob_black >= hide_thresh:
        return "HIDE"
    else:
        return "AMBIGUOUS"

def score_post(post_vec: np.ndarray,
               whitelist_vec: np.ndarray,
               blacklist_vec: np.ndarray,
               post_text: str = None,
               whitelist_words: List[str] = [],
               blacklist_words: List[str] = [],
               show_thresh: float = show_thresh,
               hide_thresh: float = hide_thresh,
               temperature: float = temperature) -> dict:
    """
    Softmax-based scoring to classify post as SHOW / HIDE / AMBIGUOUS.
    Optionally biases the probability based on keyword matches.
    Returns a dict with softmax scores, raw cosine scores, and final decision.
    """
    scores = softmax_similarity_scores(post_vec, whitelist_vec, blacklist_vec, temperature=temperature)

    if post_text:
        white_bias = keyword_match_bias(whitelist_words, post_text)
        black_bias = keyword_match_bias(blacklist_words, post_text)

        # Apply whitelist bias
        if white_bias > 0.0:
            scores["prob_white"] = min(scores["prob_white"] + white_bias, 1.0)
            scores["prob_black"] = max(1.0 - scores["prob_white"], 0.0)
            logger.debug(f"✅ Whitelist keyword bias +{white_bias:.2f} applied")

        # Apply blacklist bias
        elif black_bias > 0.0:
            scores["prob_black"] = min(scores["prob_black"] + black_bias, 1.0)
            scores["prob_white"] = max(1.0 - scores["prob_black"], 0.0)
            logger.debug(f"⚠️  Blacklist keyword bias +{black_bias:.2f} applied")

    scores["decision"] = classify_post_softmax(scores["prob_white"], scores["prob_black"],
                                               show_thresh=show_thresh,
                                               hide_thresh=hide_thresh)
    return scores
