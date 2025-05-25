import os
import logging
import sys
import signal
import threading

from server import config
from server import data_stream

from flask import Flask, jsonify, request

from server.algos import algos
from server.data_filter import operations_callback
from server.logger import logger

app = Flask(__name__)

# ───────────────────────────────────────────────────────
# Configure logging based on Flask’s debug flag
# ───────────────────────────────────────────────────────

# 1) check Flask’s own DEBUG config (set by flask --debug run)
debug_mode = app.config.get("DEBUG", False)

# 2) fallback to the FLASK_DEBUG env var if needed
if not debug_mode:
    debug_env = os.environ.get("FLASK_DEBUG", "0")
    debug_mode = debug_env.lower() in ("1", "true", "yes")

# 3) apply level to your module logger
logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

stream_stop_event = threading.Event()
stream_thread = threading.Thread(
    target=data_stream.run, args=(config.SERVICE_DID, operations_callback, stream_stop_event,)
)
stream_thread.start()


def sigint_handler(*_):
    print('Stopping data stream...')
    stream_stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_handler)


@app.route('/')
def index():
    """
    Root endpoint now calls feed.handler(). Clients can pass:
      - cursor: optional pagination cursor (string)
      - limit:  optional int, max number of posts to return
    """
    from server.algos.feed import handler
    # 2) Read query params
    cursor = request.args.get('cursor', default=None, type=str)
    limit  = request.args.get('limit',  default=20,    type=int)

    # 3) Call your feed handler
    try:
        body = handler(cursor, limit)
    except ValueError as e:
        # invalid cursor format
        return str(e), 400

    # 4) Return the dict as a JSON response
    return jsonify(body)


@app.route('/.well-known/did.json', methods=['GET'])
def did_json():
    if not config.SERVICE_DID.endswith(config.HOSTNAME):
        return '', 404

    return jsonify({
        '@context': ['https://www.w3.org/ns/did/v1'],
        'id': config.SERVICE_DID,
        'service': [
            {
                'id': '#bsky_fg',
                'type': 'BskyFeedGenerator',
                'serviceEndpoint': f'https://{config.HOSTNAME}'
            }
        ]
    })


@app.route('/xrpc/app.bsky.feed.describeFeedGenerator', methods=['GET'])
def describe_feed_generator():
    feeds = [{'uri': uri} for uri in algos.keys()]
    response = {
        'encoding': 'application/json',
        'body': {
            'did': config.SERVICE_DID,
            'feeds': feeds
        }
    }
    return jsonify(response)


@app.route('/xrpc/app.bsky.feed.getFeedSkeleton', methods=['GET'])
def get_feed_skeleton():
    feed = request.args.get('feed', default=None, type=str)
    algo = algos.get(feed)
    if not algo:
        return 'Unsupported algorithm', 400

    # Example of how to check auth if giving user-specific results:
    from server.auth import AuthorizationError, validate_auth
    try:
        requester_did = validate_auth(request)
        logger.debug(f'validate_auth() returned Requester DID: {requester_did}')
    except AuthorizationError:
        return 'Unauthorized', 401

    try:
        cursor = request.args.get('cursor', default=None, type=str)
        limit = request.args.get('limit', default=20, type=int)
        body = algo(cursor, limit)
    except ValueError:
        return 'Malformed cursor', 400

    return jsonify(body)