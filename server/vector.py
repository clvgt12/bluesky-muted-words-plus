# server/vector.py
# Vector operations using NumPy and PostgreSQL pgvector-compatible formatting

import os
import time
import numpy as np
from typing import List, Literal
from sentence_transformers import SentenceTransformer
from server.config import MODEL_NAME, SHOW_THRESH, HIDE_THRESH, TEMPERATURE, BIAS_WEIGHT
from server.logger import setup_logger
from server.text_utils import keyword_match_bias

logger = setup_logger(__name__)

_model_instance = None

def get_model() -> SentenceTransformer:
    global _model_instance
    if _model_instance is None:
        start = time.time()
        _model_instance = SentenceTransformer(
            MODEL_NAME,
            cache_folder=os.path.join(os.getcwd(), ".cache", "huggingface"), 
        )
        logger.debug(f"✅ Loaded SentenceTransformer model in {time.time() - start:.2f} seconds")
    return _model_instance

def words_to_vector(words: List[str]) -> np.ndarray:
    text = " ".join(words)
    return get_model().encode(text, show_progress_bar=False).astype(np.float32)

def string_to_vector(string: str) -> np.ndarray:
    return get_model().encode(string, show_progress_bar=False).astype(np.float32)

def vector_to_pgstring(vec: np.ndarray) -> str:
    """
    Converts a NumPy array into a PostgreSQL-compatible pgvector string.

    Args:
        vec (np.ndarray): The vector to convert.

    Returns:
        str: A string in pgvector format.
    """
    return vector_to_pg(vec.tolist())

def pgstring_to_vector(pgstring: str) -> np.ndarray:
    """
    Converts a PostgreSQL vector string into a NumPy array.

    Args:
        pgstring (str): A string in the format '[0.1, 0.2, 0.3]'.

    Returns:
        np.ndarray: The parsed NumPy array.
    """
    return np.array(pg_to_vector(pgstring), dtype=np.float32)

# Custom VectorField to support pgvector
def vector_to_pg(value):
    """
    Converts a Python list of floats to a PostgreSQL-compatible vector string.

    Args:
        value (list[float] | str): The input list to convert. If already a string, returns as-is.

    Returns:
        str: A string in pgvector format, e.g., '[0.1,0.2,0.3]'
    """
    return '[' + ','.join(map(str, value)) + ']' if isinstance(value, list) else value

def pg_to_vector(value):
    """
    Converts a string (e.g., '[0.1, 0.2, 0.3]') or a list of floats into a float list.
    Returns an empty list for None or empty values.
    """
    if value is None:
        return []
    elif isinstance(value, list):
        return value
    elif isinstance(value, str):
        # strip brackets and whitespace
        inner = value.strip('[]').strip()
        # if nothing inside (e.g. '[]'), return empty list
        if not inner:
            return []
        return [float(x) for x in inner.split(',')]
    else:
        raise TypeError(f"Unexpected vector value type: {type(value)}")

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))

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
        "raw_black": s_black,
        "temperature": temperature,
    }

def classify_post_softmax(prob_white: float, prob_black: float,
                          show_thresh: float = SHOW_THRESH,
                          hide_thresh: float = HIDE_THRESH) -> Literal["SHOW", "HIDE", "AMBIGUOUS"]:
    if prob_white > show_thresh:
        return "SHOW"
    elif prob_black > hide_thresh:
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

    Returns:
        dict: Softmax scores, raw cosine scores, thresholds, bias, and final decision.
    """
    scores = softmax_similarity_scores(post_vec, whitelist_vec, blacklist_vec, temperature=temperature)

    if post_text:
        white_bias = keyword_match_bias(whitelist_words, post_text)
        black_bias = keyword_match_bias(blacklist_words, post_text)
        if white_bias > 0.0 and black_bias > 0.0:
            logger.debug(f"⚖️  Both whitelist (+{white_bias:.2f}) and blacklist (+{black_bias:.2f}) keyword biases matched")
            net_bias = white_bias - black_bias
            scores["prob_white"] = np.clip(scores["prob_white"] + net_bias, 0.0, 1.0)
            scores["prob_black"] = 1.0 - scores["prob_white"]
        elif white_bias > 0.0:
            scores["prob_white"] = min(scores["prob_white"] + white_bias, 1.0)
            scores["prob_black"] = max(1.0 - scores["prob_white"], 0.0)
            logger.debug(f"✅ Whitelist keyword bias +{white_bias:.2f} applied")
        elif black_bias > 0.0:
            scores["prob_black"] = min(scores["prob_black"] + black_bias, 1.0)
            scores["prob_white"] = max(1.0 - scores["prob_black"], 0.0)
            logger.debug(f"⚠️  Blacklist keyword bias +{black_bias:.2f} applied")

    scores["decision"] = classify_post_softmax(scores["prob_white"], scores["prob_black"],
                                               show_thresh=show_thresh,
                                               hide_thresh=hide_thresh)

    scores["show_threshold"] = show_thresh
    scores["hide_threshold"] = hide_thresh
    scores["bias_weight"] = BIAS_WEIGHT
    return scores
