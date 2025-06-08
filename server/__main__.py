# __main__.py
import argparse
import sys
from server import config
from server.app import app, start_data_stream_thread
from waitress import serve

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

    # Start the background data stream consumer thread process
    start_data_stream_thread()

    # Start Waitress server
    serve(app, host=args.host, port=args.port, threads=args.threads)

if __name__ == '__main__':
    main()
