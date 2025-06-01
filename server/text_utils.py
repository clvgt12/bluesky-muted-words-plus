# text_utils.py
import bleach
import contractions
import ftfy
import httpx
import logging
import os
import re
import spacy
from bs4 import BeautifulSoup
from html import unescape
from dotenv import load_dotenv
from server.logger import logger
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union
from unidecode import unidecode
from urllib.parse import urlparse
from server.config import BIAS_WEIGHT

nlp = spacy.load("en_core_web_sm")

def extract_extra_text(record: Union[dict, BaseModel]) -> str:
    """
    Extracts extra natural language content from a Bluesky post record.
    Supports dicts or Pydantic models.

    Handles:
    - Link URIs from 'facets'
    - Alt-text from 'embed.images'
    - Title/description from 'embed.external' (even if nested in recordWithMedia)
    """
    extras: List[str] = []

    def safe_get(obj: Any, attr: str, default=None):
        return getattr(obj, attr, default) if not isinstance(obj, dict) else obj.get(attr, default)

    # --- Facets (inline URLs in text) ---
    facets = safe_get(record, "facets") or []
    for facet in facets:
        features = safe_get(facet, "features", [])
        for feature in features:
            if safe_get(feature, "$type") == "app.bsky.richtext.facet#link":
                uri = safe_get(feature, "uri")
                if uri:
                    extras.append(uri)

    # --- Embeds ---
    def extract_from_embed(embed: Any):
        embed_type = safe_get(embed, "$type") or safe_get(embed, "py_type", "")

        if embed_type == "app.bsky.embed.images":
            for img in safe_get(embed, "images", []):
                alt = safe_get(img, "alt", "")
                if alt:
                    extras.append(alt)

        elif embed_type == "app.bsky.embed.external":
            ext = safe_get(embed, "external", {})
            title = safe_get(ext, "title", "")
            desc = safe_get(ext, "description", "")
            url = safe_get(ext, "uri", "")
            if title:
                extras.append(clean_text(title))
            if desc:
                extras.append(clean_text(desc))
            if url:
                extras.append(clean_text(get_webpage_text(url)))

        elif embed_type == "app.bsky.embed.recordWithMedia":
            media = safe_get(embed, "media", {})
            extract_from_embed(media)

    embed = safe_get(record, "embed", {})
    extract_from_embed(embed)

    if extras:
        logger.info(f"🧠 Extracted extra text: {extras}")

    return " ".join(extras)

def clean_text(string: str) -> str:
    """
    Clean and normalize input text:
    - Strip HTML and script/style/nav tags
    - Fix Unicode, decode HTML entities
    - Expand contractions
    - Remove URLs
    - Remove punctuation
    - Collapse excess whitespace
    - Remove stopwords
    - Lemmatize nouns, verbs, adjectives, adverbs
    - Remove duplicated words
    Return string
    """
    # Strip HTML elements
    soup = BeautifulSoup(string, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)

    # Normalize
    text = ftfy.fix_text(text)
    text = unescape(text)
    text = unidecode(text)
    text = contractions.fix(text)

    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", "", text)

    # Remove punctuation (keep alphanumerics and whitespace)
    text = re.sub(r"[^\w\s]", "", text)

    # Collapse multiple whitespace and lowercase
    text = re.sub(r"\s+", " ", text).strip().lower()

    # Final tag stripping (redundant but safe)
    text = bleach.clean(text, tags=[], strip=True)

    # Tokenize, lemmatize, remove stopwords, normalize POS
    doc = nlp(text)
    cleaned_tokens = [
        token.lemma_
        for token in doc
        if token.is_alpha
        and not token.is_stop
        and token.pos_ in {"NOUN", "VERB", "ADJ", "ADV"}
    ]

    # Remove duplicated words
    seen = set()
    deduped_tokens = []
    for word in cleaned_tokens:
        if word not in seen:
            seen.add(word)
            deduped_tokens.append(word)
    
    return " ".join(deduped_tokens)

def keyword_match_bias(word_list: List[str], text: str) -> float:
    """
    Returns a bias score if any keyword exists in the text, otherwise returns 0.0.

    Parameters:
        word_list (List[str]): List of keywords to search for.
        text (str): Cleaned social media post content.

    Returns:
        float: BIAS_WEIGHT if match found, otherwise 0.0
    """

    text_words = set(re.findall(r'\b\w+\b', text.strip().lower()))
    keywords = set(word.strip().lower() for word in word_list)

    return BIAS_WEIGHT if text_words & keywords else 0.0

def get_webpage_text(url: str, timeout: float = 3.0) -> str:
    """
    Fetches a web page and returns visible text content (cleaned).
    """
    try:
        # Avoid localhost or dangerous URLs
        netloc = urlparse(url).netloc.lower()
        if not netloc or "localhost" in netloc or "127.0.0.1" in netloc:
            return ""

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://www.google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
            tag.decompose()

        return clean_text(soup.get_text(separator=" ", strip=True))

    except Exception as e:
        logger.warning(f"Failed to fetch webpage text from {url}: {e}")
        return ""
