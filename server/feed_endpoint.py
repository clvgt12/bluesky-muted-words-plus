# server/feed_endpoint.py (renamed from app.py)
import argparse
import sys
from server import config
from flask import Flask, jsonify, request
from server.algos import algos
from server.algos.feed import handler, generate_fake_jwt
from server.data_filter import operations_callback
from server.logger import setup_logger
from waitress import serve # Only needed if this file is the main entry point for waitress

app = Flask(__name__)

# ───────────────────────────────────────────────────────
# Configure logging based on Flask’s debug flag
# ───────────────────────────────────────────────────────

logger = setup_logger(__name__)

# ───────────────────────────────────────────────────────
# Removed background thread startup logic.
# These will be separate Kubernetes Deployments/CronJobs.
# ───────────────────────────────────────────────────────

# Removed sigint_handler and signal.signal calls.
# Kubernetes will send SIGTERM for graceful shutdown.

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

    if config.FLASK_ENV == "production":
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

def main():
    # Define parser and arguments
    parser = argparse.ArgumentParser(description="Start Bluesky Flask app with Waitress.")
    parser.add_argument('--host', default=config.HOST, help=f"Hostname (default: {config.HOST})")
    parser.add_argument('--port', type=int, default=int(config.PORT), help=f"Port (default: {config.PORT})")
    parser.add_argument('--threads', type=int, default=int(config.THREADS), help=f"Thread count (default: {config.THREADS})")

    # Check if user asked for help *before* parsing
    if '--help' in sys.argv or '-h' in sys.argv:
        parser.print_help()
        sys.exit(1)

    # Parse arguments normally
    args = parser.parse_args()

    # Start Waitress server
    print(f"➡️ Starting web server with host={args.host}, port={args.port} and {args.threads} threads")
    serve(app, host=args.host, port=args.port, threads=args.threads)

if __name__ == '__main__':
    main()
