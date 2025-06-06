from datetime import datetime, timezone

import peewee

db = peewee.SqliteDatabase('feed_database.db')

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
