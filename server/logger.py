# server/logger.py

import logging
import os
import sys

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        return logger  # Prevent adding handlers multiple times

    debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")

    if not debug_mode:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)  # silence completely
        logging.getLogger("httpx").setLevel(logging.ERROR)  # silence completely
        
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if debug_mode else logging.ERROR)

    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
