# server/logger.py

import logging
import os
import sys
from server.config import FLASK_DEBUG

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if FLASK_DEBUG else logging.ERROR)

    if logger.hasHandlers():
        return logger  # Prevent adding handlers multiple times

    if not FLASK_DEBUG:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)  # silence completely
        logging.getLogger("httpx").setLevel(logging.ERROR)  # silence completely

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if FLASK_DEBUG else logging.ERROR)

    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
