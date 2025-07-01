# server/config.py
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv # Keep dotenv imports for conditional use

# Load from .env.development only if FLASK_ENV is 'development'
# In production K8s, FLASK_ENV will NOT be 'development', so .env files won't be loaded.
FLASK_ENV = os.environ.get('FLASK_ENV','production')
if FLASK_ENV == 'development':
    # Ensure this points to your dev .env file if it's named differently
    dotenv_path = Path(".env.development")
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)
    else:
        # Fallback for general .env if .env.development is not found
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
    # In a K8s deployment, you might manage this differently (e.g., dynamic registration)
    # For now, it might be expected to be set by the environment or removed if not needed for the specific K8s component.
    # For local dev, you'd publish it once and set it.
    pass # Temporarily pass for refactoring flexibility, but remember it's a critical config


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

# Database connection parameters (will be set by K8s Secrets/ConfigMaps)
POSTGRES_DB = os.getenv("POSTGRES_DB", "feed_database")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1") # <<-- CHANGED DEFAULT FOR K8S
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432)) # <<-- CHANGED DEFAULT TO INT

# Application server parameters (relevant for Flask app component)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
THREADS = int(os.getenv("THREADS", 4))

# Database TTL cleanup parameters (relevant for cleanup job component)
DB_RECORD_TTL = int(os.getenv("DB_RECORD_TTL", 1800))
DB_THREAD_HYSTERESIS = int(os.getenv("DB_THREAD_HYSTERESIS", 15)) # This might become irrelevant for CronJob

# Model parameters (relevant for feed-generator and user-list-tool)
MODEL_NAME = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
SHOW_THRESH = min(max(float(os.getenv("SHOW_THRESHOLD", 0.75)), 0.0), 1.0)
HIDE_THRESH = min(max(float(os.getenv("HIDE_THRESHOLD", 0.75)), 0.0), 1.0)
AMBIGUOUS_POST_POLICY = os.getenv("AMBIGUOUS_POST_POLICY", "SHOW")
AMBIGUOUS_POST_POLICY = AMBIGUOUS_POST_POLICY if AMBIGUOUS_POST_POLICY in ("SHOW", "HIDE") else "SHOW"
BIAS_WEIGHT = float(os.getenv("BIAS_WEIGHT", "0.05"))
TEMPERATURE = float(os.getenv("SOFTMAX_TEMPERATURE", 1.0))
# Clamp temperature to safe minimum value
if TEMPERATURE <= 0.0:
    TEMPERATURE = 0.1