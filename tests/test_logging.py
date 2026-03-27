"""Tests for structured JSON logging."""
import json
import logging

import pytest

from saas.logging import JSONFormatter, setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """Save and restore root logger state around each test."""
    root = logging.getLogger()
    original_level = root.level
    original_handlers = root.handlers[:]
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


def _make_record(msg="test message", level=logging.INFO, **extra):
    """Create a LogRecord with optional extra fields."""
    record = logging.LogRecord(
        name="test.logger",
        level=level,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for key, val in extra.items():
        setattr(record, key, val)
    return record


class TestJSONFormatter:
    def test_produces_valid_json(self):
        formatter = JSONFormatter()
        record = _make_record("hello world")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["msg"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert "ts" in parsed

    def test_includes_extra_fields(self):
        formatter = JSONFormatter()
        record = _make_record(
            "gpu provisioned",
            job_id=42,
            pod_id="abc-123",
            event="gpu_provisioned",
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["job_id"] == 42
        assert parsed["pod_id"] == "abc-123"
        assert parsed["event"] == "gpu_provisioned"

    def test_excludes_none_extra_fields(self):
        formatter = JSONFormatter()
        record = _make_record("simple log")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "job_id" not in parsed
        assert "pod_id" not in parsed

    def test_includes_exception(self):
        formatter = JSONFormatter()
        record = _make_record("error occurred")
        try:
            raise ValueError("something broke")
        except ValueError:
            import sys
            record.exc_info = sys.exc_info()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "something broke" in parsed["exception"]


class TestSetupLogging:
    def test_json_mode(self):
        setup_logging(json_output=True)
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_text_mode(self):
        setup_logging(json_output=False)
        root = logging.getLogger()
        assert len(root.handlers) == 1
        formatter = root.handlers[0].formatter
        assert not isinstance(formatter, JSONFormatter)
        assert isinstance(formatter, logging.Formatter)

    def test_sets_log_level(self):
        setup_logging(level="DEBUG", json_output=True)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_clears_duplicate_handlers(self):
        setup_logging(json_output=True)
        setup_logging(json_output=True)
        root = logging.getLogger()
        assert len(root.handlers) == 1
