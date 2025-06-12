# server/database.py
from datetime import datetime, timedelta, timezone

import peewee
import time

import numpy as np
from server.config import DEFAULT_DID, DB_RECORD_TTL, DB_THREAD_HYSTERESIS
from server.logger import setup_logger

logger = setup_logger(__name__)

db = peewee.SqliteDatabase('feed_database.db')

# Ensure WAL mode is enabled after connecting
@db.connection_context()
def configure_sqlite():
    journal_mode = db.execute_sql("PRAGMA journal_mode=WAL;").fetchone()[0]
    db.execute_sql("PRAGMA synchronous = NORMAL;")   # Less fsync = faster writes
    db.execute_sql("PRAGMA cache_size = -10000;")    # ~10MB cache (in KB if negative)

    logger.debug(f"SQLite PRAGMA settings: journal_mode={journal_mode}, synchronous=NORMAL, cache_size=-10000")

configure_sqlite()

class BaseModel(peewee.Model):
    class Meta:
        database = db

class Post(BaseModel):
    uri = peewee.CharField(index=True)
    cid = peewee.CharField()
    reply_parent = peewee.CharField(null=True, default=None)
    reply_root = peewee.CharField(null=True, default=None)
    indexed_at = peewee.DateTimeField(
        default=lambda: datetime.now(timezone.utc),
        formats=["%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z"],
    )

class SubscriptionState(BaseModel):
    service = peewee.CharField(unique=True)
    cursor = peewee.BigIntegerField()

class PostVector(BaseModel):
    post = peewee.ForeignKeyField(Post, backref='vector', unique=True)
    post_text = peewee.CharField(null=True, default=None)
    post_vector = peewee.BlobField(null=True, default=None)
    post_dim = peewee.BigIntegerField(null=True, default=None)

class UserLists(BaseModel):
    did = peewee.CharField(index=True)
    white_list_text = peewee.TextField(null=True)
    white_list_urls = peewee.TextField(null=True)
    white_list_vector = peewee.BlobField(null=True)
    white_list_dim = peewee.IntegerField(null=True)
    black_list_text = peewee.TextField(null=True)
    black_list_urls = peewee.TextField(null=True)
    black_list_vector = peewee.BlobField(null=True)
    black_list_dim = peewee.IntegerField(null=True)
    modified_at = peewee.DateTimeField(default=lambda: datetime.now(timezone.utc))

if db.is_closed():
    db.connect()
    # Drop only the specified tables
    db.drop_tables([PostVector, SubscriptionState, Post])  # Drop in reverse dependency order
    db.create_tables([Post, SubscriptionState, PostVector, UserLists])

def fetch_user_lists_fields(did: str) -> tuple[str, np.ndarray, int, str, np.ndarray, int]:
    try:
        row = UserLists.get_or_none(UserLists.did == DEFAULT_DID)
    except UserLists.DoesNotExist:
        logger.error(f'🚫 ERROR! white and black lists do not exist for user {user_did} !!!')
        return None
    white_vec = np.frombuffer(row.white_list_vector, dtype=np.float32, count=row.white_list_dim)
    black_vec = np.frombuffer(row.black_list_vector, dtype=np.float32, count=row.black_list_dim)
    return row.white_list_text, white_vec, row.white_list_dim, row.black_list_text, black_vec, row.black_list_dim

def cleanup_expired_posts(ttl_seconds: int=DB_RECORD_TTL, hysteresis_seconds: int = DB_THREAD_HYSTERESIS):
    """Background task that removes expired Post and PostVector entries based on TTL."""
    while True:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=ttl_seconds)

        # Delete PostVectors for expired posts
        expired_posts = Post.select().where(Post.indexed_at < cutoff)
        expired_post_ids = [post.id for post in expired_posts]
        if expired_post_ids:
            PostVector.delete().where(PostVector.post_id.in_(expired_post_ids)).execute()
            Post.delete().where(Post.id.in_(expired_post_ids)).execute()
            logger.info(f"[TTL Cleanup] Deleted {len(expired_post_ids)} expired posts at {datetime.now(timezone.utc)}")

        # Sleep before next run
        time.sleep(ttl_seconds + hysteresis_seconds)