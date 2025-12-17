import logging
import sys
import os
import json
from datetime import datetime
from pytz import timezone
from logging.handlers import TimedRotatingFileHandler
from flask import has_request_context, request
import inspect

# Define Karachi timezone
KARACHI_TZ = timezone("Asia/Karachi")

# ANSI color codes
LOG_COLORS = {
    "DEBUG": "\033[90m",     # Grey
    "INFO": "\033[96m",      # Cyan
    "WARNING": "\033[93m",   # Yellow
    "ERROR": "\033[91m",     # Red
    "CRITICAL": "\033[41m",  # Red background
    "RESET": "\033[0m"
}

class JsonFormatter(logging.Formatter):
    def __init__(self, use_color=False):
        super().__init__()
        self.use_color = use_color

    def format(self, record):
        log_time = datetime.now(KARACHI_TZ).strftime("%H:%M:%S")
        log_record = {
            "level": record.levelname,
            "timestamp": log_time,
            "module": record.module,
            "caller": getattr(record, "caller", None),
            "message": record.getMessage(),
            "actor_type": getattr(record, "actor_type", "system"),
            "action_type": getattr(record, "action_type", "event"),
            "user_id": getattr(record, "user_id", "system"),
            "ip": getattr(record, "ip", "system"),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        json_log = json.dumps(log_record)

        if self.use_color:
            color = LOG_COLORS.get(record.levelname, "")
            reset = LOG_COLORS["RESET"]
            return f"{color}{json_log}{reset}"
        else:
            return json_log

class ContextFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.ip = request.remote_addr
        else:
            record.ip = "system"
        return True

def setup_logging(level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)

    if logger.hasHandlers():
        logger.handlers.clear()

    context_filter = ContextFilter()

    # Create logs folder
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Filename with Karachi time
    timestamp = datetime.now(KARACHI_TZ).strftime("%Y-%m-%d_%H")
    file_path = os.path.join(log_dir, f"{timestamp}.log")

    # File handler (no color)
    file_handler = TimedRotatingFileHandler(
        filename=file_path, when="H", interval=1, backupCount=48, utc=False
    )
    file_handler.setFormatter(JsonFormatter(use_color=False))
    file_handler.addFilter(context_filter)
    logger.addHandler(file_handler)

    # Stream handler (with color)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JsonFormatter(use_color=True))
    stream_handler.addFilter(context_filter)
    logger.addHandler(stream_handler)

    return logger

# Logging helper
def log_action(message, user_id=None, actor_type="user", action_type="event", level="info", exc_info=None):
    logger = logging.getLogger()
    frame = inspect.stack()[1]
    filename = os.path.basename(frame.filename)
    function_name = frame.function

    extra = {
        "user_id": user_id or "system",
        "actor_type": actor_type,
        "action_type": action_type,
        "caller": f"{filename}:{function_name}"
    }

    if level == "error":
        logger.error(message, extra=extra, exc_info=exc_info)
    else:
        logger.info(message, extra=extra)
from functools import wraps
from flask import jsonify
from sqlalchemy.exc import OperationalError




def log_exceptions(route_name=None):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except OperationalError as oe:
                log_action(
                    f"❌ Database connection lost in route: {route_name or func.__name__}",
                    level="error",
                    exc_info=True
                )
                return jsonify({"success": False, "message": "Database connection error. Please try again later."}), 503
            except Exception:
                log_action(
                    f"❌ Exception in route: {route_name or func.__name__}",
                    level="error",
                    exc_info=True
                )
                return jsonify({"success": False, "message": "Internal server error"}), 500
        return inner
    return wrapper