# server/post_ingestion_service_main.py (new file)
import time
import sys
import signal
import threading # Still used for the stop event for data_stream.run
from server import config
from server import data_stream
from server.data_filter import operations_callback
from server.logger import setup_logger

logger = setup_logger(__name__)

# Event to signal the data stream thread to stop gracefully
data_stream_stop_event = threading.Event()

def sigterm_handler(*_):
    """Handles SIGTERM to gracefully stop the ingestion thread."""
    logger.info('Received SIGTERM. Stopping data stream...')
    data_stream_stop_event.set()
    # Give the thread a moment to finish its current loop iteration
    time.sleep(5) # Give it a few seconds to exit gracefully
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, sigterm_handler) # For local Ctrl+C
signal.signal(signal.SIGTERM, sigterm_handler) # For Kubernetes/Docker SIGTERM

def main():
    logger.info("➡️ Starting Bluesky Firehose Ingestion Service")
    # The data_stream.run function already has a loop and handles reconnection
    # Pass the stop event for graceful shutdown.
    data_stream.run(
        name="bluesky-firehose-ingestion", # A unique name for this service's cursor
        operations_callback=operations_callback,
        stream_stop_event=data_stream_stop_event
    )
    logger.info("Bluesky Firehose Ingestion Service stopped.")

if __name__ == '__main__':
    main()