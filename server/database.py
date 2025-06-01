# server/database.py
from datetime import datetime, timezone

import peewee

import numpy as np
from server.config import DEFAULT_DID

db = peewee.SqliteDatabase('feed_database.db')

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
    white_list_text = peewee.CharField(null=True, default=None)
    white_list_vector = peewee.BlobField(null=True, default=None)
    white_list_dim = peewee.BigIntegerField(null=True, default=None)
    black_list_text = peewee.CharField(null=True, default=None)
    black_list_vector = peewee.BlobField(null=True, default=None)
    black_list_dim = peewee.BigIntegerField(null=True, default=None)
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
