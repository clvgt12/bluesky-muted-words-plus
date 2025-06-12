# app.py 
import sys
import signal
import threading

from server import config
from server import data_stream

from flask import Flask, jsonify, request
from server.algos import algos
from server.algos.feed import handler, generate_fake_jwt
from server.data_filter import operations_callback
from server.database import cleanup_expired_posts
from server.logger import setup_logger

app = Flask(__name__)

# ───────────────────────────────────────────────────────
# Configure logging based on Flask’s debug flag
# ───────────────────────────────────────────────────────

logger = setup_logger(__name__)  # 👈 This tags the logger with the module path

# ───────────────────────────────────────────────────────
# Start a database TTL cleanup thread
# ───────────────────────────────────────────────────────

database_ttl_cleanup_stop_event = threading.Event()

def start_database_ttl_cleanup_thread():
    ttl_thread = threading.Thread(
        target=cleanup_expired_posts,
        args=(),
        daemon=True  # so it won't block shutdown
    )
    ttl_thread.start()
    return ttl_thread

# ───────────────────────────────────────────────────────
# Configure and start the data stream in a separate thread
# ───────────────────────────────────────────────────────

data_stream_stop_event = threading.Event()

def start_data_stream_thread():
    data_stream_thread = threading.Thread(
        target=data_stream.run,
        args=(config.SERVICE_DID, operations_callback, data_stream_stop_event),
        daemon=True,
    )
    data_stream_thread.start()
    return data_stream_thread

def sigint_handler(*_):
    print('Stopping background threads...')
    database_ttl_cleanup_stop_event.set()
    data_stream_stop_event.set()
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)

# ───────────────────────────────────────────────────────
# Define REST API and enter event loop
# ───────────────────────────────────────────────────────

@app.route('/')
def index():
    """
    Root endpoint shows the application name DISPLAY_NAME and
    description DESCRIPTION used when the custom feed registers 
    itself on the Bluesky network
    """
    if not config.DISPLAY_NAME or not config.DESCRIPTION:
        return '', 404
    return jsonify({
        'DISPLAY_NAME': config.DISPLAY_NAME,
        'DESCRIPTION': config.DESCRIPTION,
    })

@app.route("/health/")
def health():
    return jsonify({
        'Status': 'OK'
    }), 200

@app.route('/test-feed-handler/', methods=['GET'])
def test_feed_handler():
    """
    Tests feed.handler(). Clients can pass:
      - cursor: optional pagination cursor (string)
      - limit:  optional int, max number of posts to return

    Injects a fake Authorization header using DEFAULT_DID.
    """
    
    if not config.FLASK_DEBUG:
        return jsonify({"error": "Test handler is disabled in production"}), 403

    # 1) Extract query params
    cursor = request.args.get('cursor', default=None, type=str)
    limit  = request.args.get('limit',  default=20,    type=int)

    # 2) Use DEFAULT_DID for spoofed user identity
    fake_token = generate_fake_jwt(config.DEFAULT_DID, config.SERVICE_DID)

    # 3) Inject Authorization header into WSGI environ
    request.environ['HTTP_AUTHORIZATION'] = f"Bearer {fake_token}"

    # 4) Call handler and return result
    try:
        response = handler(cursor, limit)
    except ValueError as e:
        return str(e), 400

    return response

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
    except AuthorizationError:
        return 'Unauthorized', 401

    # Now check if the DID is in the UserList table
    from server.database import UserLists
    if not UserLists.select().where(UserLists.did == requester_did).exists():
        return 'Unauthorized', 401
        
    try:
        cursor = request.args.get('cursor', default=None, type=str)
        limit = request.args.get('limit', default=20, type=int)
        body = algo(cursor, limit)
    except ValueError:
        return 'Malformed cursor', 400

    return jsonify(body)
