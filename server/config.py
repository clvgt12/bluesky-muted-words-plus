# config.py
import os
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

# Load from .env.development only if available — this supports local dev, but is safe in prod
if Path(".env.development").exists():
    load_dotenv(dotenv_path=".env.development", override=False)
else:
    load_dotenv(override=False)

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
DISPLAY_NAME = os.getenv("DISPLAY_NAME")
DESCRIPTION = os.getenv("DESCRIPTION")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
THREADS = int(os.getenv("THREADS", 4))
MODEL_NAME = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
SHOW_THRESH = min(max(float(os.getenv("SHOW_THRESHOLD", 0.75)), 0.0), 1.0)
HIDE_THRESH = min(max(float(os.getenv("HIDE_THRESHOLD", 0.75)), 0.0), 1.0)
BIAS_WEIGHT = float(os.getenv("BIAS_WEIGHT", "0.05"))
TEMPERATURE = float(os.getenv("SOFTMAX_TEMPERATURE", 1.0))
# Clamp temperature to safe minimum value
if TEMPERATURE <= 0.0:
    TEMPERATURE = 0.1
