"""Structured JSON logging for FishCloud."""
import json
import logging
import re
import sys
from datetime import datetime, timezone

REDACT_FIELDS = {"seed_text", "llm_api_key", "zep_api_key", "api_key", "secret_key", "password", "token"}
REDACT_PATTERNS = {"key", "secret", "password", "token"}


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": self._redact_message(record.getMessage()),
        }
        # Merge any extra structured fields passed via `extra={}`
        _KNOWN_FIELDS = frozenset((
            "job_id", "pod_id", "stage", "elapsed_s", "provider",
            "gpu_type", "event", "error", "credits", "user_id",
            "session_id", "pack_id", "retry", "duration_s",
        ))
        for key in _KNOWN_FIELDS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        # Also capture any sensitive fields that were passed via extra={}
        # so we can redact them rather than silently dropping them
        for key in REDACT_FIELDS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        # Redact sensitive values
        for key in list(log_entry.keys()):
            if key in REDACT_FIELDS or any(p in key.lower() for p in REDACT_PATTERNS):
                log_entry[key] = "[REDACTED]"
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)

    def _redact_message(self, msg: str) -> str:
        """Redact API keys and long base64-like strings from log messages."""
        # Redact anything that looks like an API key (sk-, ghp_, zep_, etc.)
        msg = re.sub(r'(sk-|ghp_|zep_)[A-Za-z0-9_-]{10,}', r'\1[REDACTED]', msg)
        return msg


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
