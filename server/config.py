# config.py
import logging
import os
from dotenv import load_dotenv

load_dotenv()

SERVICE_DID = os.environ.get('SERVICE_DID')
HOSTNAME = os.environ.get('HOSTNAME')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', '0').lower() in ("1", "true", "yes")
FLASK_RUN_FROM_CLI = os.environ.get('FLASK_RUN_FROM_CLI','0').lower() in ("1", "true", "yes")

if not HOSTNAME:
    raise RuntimeError('You should set "HOSTNAME" environment variable first.')

if not SERVICE_DID:
    SERVICE_DID = f'did:web:{HOSTNAME}'


FEED_URI = os.environ.get('FEED_URI')
if not FEED_URI:
    raise RuntimeError('Publish your feed first (run publish_feed.py) to obtain Feed URI. '
                       'Set this URI to "FEED_URI" environment variable.')


def _get_bool_env_var(value: str) -> bool:
    if value is None:
        return False

    normalized_value = value.strip().lower()
    if normalized_value in {'1', 'true', 't', 'yes', 'y'}:
        return True

    return False


IGNORE_ARCHIVED_POSTS = _get_bool_env_var(os.environ.get('IGNORE_ARCHIVED_POSTS'))
IGNORE_REPLY_POSTS = _get_bool_env_var(os.environ.get('IGNORE_REPLY_POSTS'))

BSKY_USERNAME = os.getenv("HANDLE")
BSKY_PASSWORD = os.getenv("PASSWORD")
DEFAULT_DID = os.getenv("DEFAULT_DID")
MODEL_NAME = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
SHOW_THRESH = float(os.getenv("SHOW_THRESHOLD", 0.75))
HIDE_THRESH = float(os.getenv("HIDE_THRESHOLD", 0.75))
BIAS_WEIGHT = float(os.getenv("BIAS_WEIGHT", "0.05"))
TEMPERATURE = float(os.getenv("SOFTMAX_TEMPERATURE", 1.0))
