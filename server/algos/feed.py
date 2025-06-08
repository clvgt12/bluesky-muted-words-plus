# server/algos/feed.py
import jwt
import time
from datetime import datetime
from flask import Response, request, jsonify
from typing import Optional

from server import config
from server.auth import validate_auth, AuthorizationError
from server.database import Post, UserLists

uri = config.FEED_URI
CURSOR_EOF = 'eof'


def generate_fake_jwt(user_did: str, aud_did: str) -> str:
    return f"dev:{user_did}"  # Unsafe, for testing only

def handler(cursor: Optional[str], limit: int) -> Response:

    try:
        user_did = validate_auth(request)
    except AuthorizationError as e:
        return jsonify({"error": str(e)}), 403

    if not UserLists.select().where(UserLists.did == user_did).exists():
        return jsonify({"error": "Not authorized"}), 403

    posts = Post.select().order_by(Post.cid.desc(), Post.indexed_at.desc()).limit(limit)

    if cursor:
        if cursor == CURSOR_EOF:
            return jsonify({
                'cursor': CURSOR_EOF,
                'feed': []
            }), 200
        cursor_parts = cursor.split('::')
        if len(cursor_parts) != 2:
            raise ValueError('Malformed cursor')

        indexed_at, cid = cursor_parts
        indexed_at = datetime.fromtimestamp(int(indexed_at) / 1000)
        posts = posts.where(
            ((Post.indexed_at == indexed_at) & (Post.cid < cid)) |
            (Post.indexed_at < indexed_at)
        )

    feed = [{'post': post.uri} for post in posts]

    last_post = None
    for p in reversed(posts):
        last_post = p
        break

    new_cursor = CURSOR_EOF
    if last_post:
        new_cursor = f'{int(last_post.indexed_at.timestamp() * 1000)}::{last_post.cid}'

    return jsonify({
        'cursor': new_cursor,
        'feed': feed
    }), 200
