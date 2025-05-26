# text_utils.py
import bleach
import contractions
import ftfy
import re
from bs4 import BeautifulSoup
from html import unescape
from typing import List, Optional, Any
from unidecode import unidecode

# Clean text
def clean_text(string: str) -> str:
    """
    Slogan: Clean text.
    """
    soup = BeautifulSoup(string, "html.parser")
    for tag in soup(["script","style","header","footer","nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)

    # Unicode fixes
    text = ftfy.fix_text(text)
    text = unescape(text)
    text = unidecode(text)
    text = contractions.fix(text)

    # Remove URLs, collapse whitespace
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Final tag stripping & cleanup
    text = bleach.clean(text, tags=[], strip=True)
    return text

def keyword_match_exists(word_list: List[str], text: str) -> int:
    """
    Slogan: Returns 1 if at least one keyword exists in the text string, else 0.

    Parameters:
        word_list (List[str]): List of keywords to search for.
        text (str): Cleaned social media post content.

    Returns:
        int: 1 if match found, 0 otherwise.
    """
    text_words = set(re.findall(r'\b\w+\b', text.strip().lower()))  # tokenize and normalize text
    keywords = set(word.strip().lower() for word in word_list)      # normalize keywords
    return int(bool(text_words & keywords))                 # intersection check
