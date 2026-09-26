import logging
import sys
import json
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    """
    Structured JSON log formatter for production observability.
    Masks sensitive values automatically.
    """
    SENSITIVE_KEYS = {"password", "secret", "token", "access_token", "refresh_token", "api_key", "authorization"}

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
            
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            sanitized = {}
            for k, v in record.extra_data.items():
                if any(s in k.lower() for s in self.SENSITIVE_KEYS):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = v
            log_entry["data"] = sanitized

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)

def setup_logging(level: str = "INFO"):
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger

logger = setup_logging()
