# server/cleanup_expired_posts_main.py (new file)
import sys
from server.database import cleanup_expired_posts
from server.logger import setup_logger
from server import config # Import config to get DB_RECORD_TTL

logger = setup_logger(__name__)

def main():
    logger.info("➡️ Starting Database TTL Cleanup Job")
    # Call the cleanup function with the configured TTL
    cleanup_expired_posts(ttl_seconds=config.DB_RECORD_TTL)
    logger.info("Database TTL Cleanup Job completed.")
    sys.exit(0) # Ensure the script exits after execution

if __name__ == '__main__':
    main()
