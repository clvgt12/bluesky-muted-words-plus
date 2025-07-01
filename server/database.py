# server/database.py
from datetime import datetime, timedelta, timezone
import time
import numpy as np
import peewee
from playhouse.postgres_ext import PostgresqlExtDatabase
from server.config import DEFAULT_DID, DB_RECORD_TTL, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
from server.logger import setup_logger
from server.vector import pgstring_to_vector, vector_to_pgstring

logger = setup_logger(__name__)

# Configure PostgreSQL database connection
db = PostgresqlExtDatabase(
    POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    host=POSTGRES_HOST,
    port=POSTGRES_PORT
)

class VectorField(peewee.Field):
    field_type = 'vector'

    # when writing a numpy array (or a list) into Postgres…
    def db_value(self, value):
        # always emit a string "[x1,x2,…]" no matter if `value` is list or np.ndarray
        return vector_to_pgstring(value)

    # when reading back from Postgres (you’ll get a string "[x1,x2,…]")
    def python_value(self, value):
        # parse it straight into a numpy array
        return pgstring_to_vector(value)

class BaseModel(peewee.Model):
    class Meta:
        database = db

class Post(BaseModel):
    uri = peewee.CharField(index=True)
    cid = peewee.CharField()
    reply_parent = peewee.CharField(null=True, default=None)
    reply_root = peewee.CharField(null=True, default=None)
    indexed_at = peewee.DateTimeField(default=lambda: datetime.now(timezone.utc))

class SubscriptionState(BaseModel):
    service = peewee.CharField(unique=True)
    cursor = peewee.BigIntegerField()

class UserLists(BaseModel):
    did = peewee.CharField(index=True)
    white_list_text = peewee.TextField(null=True)
    white_list_urls = peewee.TextField(null=True)
    white_list_vector = VectorField(null=True)
    white_list_dim = peewee.IntegerField(null=True)
    black_list_text = peewee.TextField(null=True)
    black_list_urls = peewee.TextField(null=True)
    black_list_vector = VectorField(null=True)
    black_list_dim = peewee.IntegerField(null=True)
    modified_at = peewee.DateTimeField(default=lambda: datetime.now(timezone.utc))

if db.is_closed():
    db.connect()
    db.create_tables([Post, SubscriptionState, UserLists])

class UserListNotFoundError(Exception):
    """Raised when whitelist/blacklist vectors for a user are missing."""
    def __init__(self, did: str):
        super().__init__(f"Whitelist/blacklist vectors do not exist for user DID: {did}")

def fetch_user_lists_fields(did: str):
    """
    Retrieve the whitelist and blacklist vectors and metadata for a specific user.

    Args:
        did (str): The decentralized identifier of the user.

    Returns:
        tuple[str, np.ndarray, int, str, np.ndarray, int] | None:
            A tuple containing:
            - white_list_text (str): Raw whitelist input text.
            - white_list_urls (List[str]): List of URL strings, contents vectorized into white_list_vector
            - white_list_vector (np.ndarray): Whitelist vector as a NumPy array.
            - white_list_dim (int): Dimensionality of the whitelist vector.
            - black_list_text (str): Raw blacklist input text.
            - black_list_urls (List[str]): List of URL strings, contents vectorized into black_list_vector
            - black_list_vector (np.ndarray): Blacklist vector as a NumPy array.
            - black_list_dim (int): Dimensionality of the blacklist vector.

            Returns None if the user record does not exist or an error occurs.
    """
    row = UserLists.get_or_none(UserLists.did == did)
    if not row:
        logger.error(f"Whitelist/blacklist vectors do not exist for user DID: {did}")
        raise UserListNotFoundError(did)

    return (
        row.white_list_text,
        row.white_list_urls,
        row.white_list_vector,
        row.white_list_dim,
        row.black_list_text,
        row.black_list_urls,
        row.black_list_vector,
        row.black_list_dim
    )

def cleanup_expired_posts(ttl_seconds: int = DB_RECORD_TTL): 
    """
    Deletes expired Post entries based on a configurable TTL.

    Args:
        ttl_seconds (int): Time-to-live in seconds for Post entries before deletion.

    Behavior:
        Deletes posts older than `ttl_seconds`. Designed to be called once by a job.
    """
    logger.info(f"➡️ [TTL Cleanup] Starting cleanup process for posts older than {ttl_seconds} seconds.")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=ttl_seconds)

    # Use a more efficient deletion if possible, or paginated deletion for very large tables
    deleted_count = Post.delete().where(Post.indexed_at < cutoff).execute()
    logger.info(f"✅ [TTL Cleanup] Deleted {deleted_count} expired posts at {datetime.now(timezone.utc)}")