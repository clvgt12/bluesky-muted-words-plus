# vector.py
# Vector operations using NumPy

import logging
import os
import numpy as np
from typing import List, Literal
from sentence_transformers import SentenceTransformer
from server.config import MODEL_NAME, SHOW_THRESH, HIDE_THRESH, TEMPERATURE
from server.logger import logger
from server.text_utils import keyword_match_bias

model = SentenceTransformer(MODEL_NAME)

# Enforce limits
SHOW_THRESH = min(max(SHOW_THRESH, 0.0), 1.0)
HIDE_THRESH = min(max(HIDE_THRESH, 0.0), 1.0)

# Clamp temperature to safe minimum value
if TEMPERATURE <= 0.0:
    logger.error("⚠️  SOFTMAX_TEMPERATURE must be > 0. Defaulting to 1.0.")
    TEMPERATURE = 1.0

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
                              temperature: float = TEMPERATURE) -> dict:
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
                          show_thresh: float = SHOW_THRESH,
                          hide_thresh: float = HIDE_THRESH) -> Literal["SHOW", "HIDE", "AMBIGUOUS"]:
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
               show_thresh: float = SHOW_THRESH,
               hide_thresh: float = HIDE_THRESH,
               temperature: float = TEMPERATURE) -> dict:
    """
    Softmax-based scoring to classify post as SHOW / HIDE / AMBIGUOUS.
    Optionally biases the probability based on keyword matches.
    Returns a dict with softmax scores, raw cosine scores, and final decision.
    """
    scores = softmax_similarity_scores(post_vec, whitelist_vec, blacklist_vec, temperature=TEMPERATURE)

    if post_text:
        white_bias = keyword_match_bias(whitelist_words, post_text)
        black_bias = keyword_match_bias(blacklist_words, post_text)
        # If both biases apply
        if white_bias > 0.0 and black_bias > 0.0:
            logger.info(f"⚖️  Both whitelist (+{white_bias:.2f}) and blacklist (+{black_bias:.2f}) keyword biases matched")
            net_bias = white_bias - black_bias
            scores["prob_white"] = np.clip(scores["prob_white"] + net_bias, 0.0, 1.0)
            scores["prob_black"] = 1.0 - scores["prob_white"]
        # Apply whitelist bias
        elif white_bias > 0.0:
            scores["prob_white"] = min(scores["prob_white"] + white_bias, 1.0)
            scores["prob_black"] = max(1.0 - scores["prob_white"], 0.0)
            logger.info(f"✅ Whitelist keyword bias +{white_bias:.2f} applied")
        # Apply blacklist bias
        elif black_bias > 0.0:
            scores["prob_black"] = min(scores["prob_black"] + black_bias, 1.0)
            scores["prob_white"] = max(1.0 - scores["prob_black"], 0.0)
            logger.info(f"⚠️  Blacklist keyword bias +{black_bias:.2f} applied")

    scores["decision"] = classify_post_softmax(scores["prob_white"], scores["prob_black"],
                                               show_thresh=SHOW_THRESH,
                                               hide_thresh=HIDE_THRESH)
    return scores
