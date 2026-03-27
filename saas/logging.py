"""Structured JSON logging for FishCloud."""
import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge any extra structured fields passed via `extra={}`
        for key in ("job_id", "pod_id", "stage", "elapsed_s", "provider",
                     "gpu_type", "event", "error", "credits", "user_id",
                     "session_id", "pack_id", "retry", "duration_s"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure root logger with JSON or plain text output.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, use JSONFormatter. If False, use standard format.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
    root.addHandler(handler)
