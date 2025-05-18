# app/__init__.py
import os
import logging
from flask import Flask

app = Flask(__name__)

# 1. Read Flask’s debug setting
debug_mode = app.config.get("DEBUG", False)
# 2. Fall back to FLASK_DEBUG env var if needed
if not debug_mode and os.environ.get("FLASK_DEBUG", "0") in ("1","true","True"):
    debug_mode = True

# 3. Configure your logger
from server.logger import logger
logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
