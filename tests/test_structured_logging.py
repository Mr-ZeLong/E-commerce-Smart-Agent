"""Tests for structured JSON logging.

Validates ``JsonFormatter`` output schema and ``configure_logging`` behavior.
"""

import json
import logging
import sys

from app.core.structured_logging import JsonFormatter, SafeTextFormatter, configure_logging


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class TestJsonFormatter:
    def test_outputs_valid_json(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        line = formatter.format(record)
        parsed = json.loads(line)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "hello world"
        assert parsed["source_file"] == "/path/to/test.py"
        assert parsed["line_number"] == 42
        assert "timestamp" in parsed

    def test_includes_correlation_id_when_present(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=1,
            msg="warn",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc-123"
        line = formatter.format(record)
        parsed = json.loads(line)
        assert parsed["correlation_id"] == "abc-123"

    def test_omits_correlation_id_when_dash(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="info",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "-"
        line = formatter.format(record)
        parsed = json.loads(line)
        assert "correlation_id" not in parsed

    def test_includes_stack_trace_on_exception(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=1,
                msg="error",
                args=(),
                exc_info=exc_info,
            )
        line = formatter.format(record)
        parsed = json.loads(line)
        assert "stack_trace" in parsed
        assert "ValueError: boom" in parsed["stack_trace"]

    def test_extra_fields_are_included(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="info",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"
        line = formatter.format(record)
        parsed = json.loads(line)
        assert parsed["custom_field"] == "custom_value"


class TestSafeTextFormatter:
    def test_defaults_correlation_id_to_dash(self):
        formatter = SafeTextFormatter("%(correlation_id)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        text = formatter.format(record)
        assert text == "- - hello"

    def test_preserves_existing_correlation_id(self):
        formatter = SafeTextFormatter("%(correlation_id)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "xyz"
        text = formatter.format(record)
        assert text == "xyz - hello"


class TestConfigureLogging:
    def _find_stream_handler(self, logger):
        for h in logger.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler):
                return h
        return None

    def test_json_format_configures_json_formatter(self):
        configure_logging(log_format="json")
        root = logging.getLogger()
        handler = self._find_stream_handler(root)
        assert handler is not None
        assert isinstance(handler.formatter, JsonFormatter)

    def test_text_format_configures_text_formatter(self):
        configure_logging(log_format="text")
        root = logging.getLogger()
        handler = self._find_stream_handler(root)
        assert handler is not None
        assert isinstance(handler.formatter, SafeTextFormatter)

    def test_uvicorn_loggers_receive_same_handler(self):
        configure_logging(log_format="json")
        for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
            logger = logging.getLogger(name)
            assert any(
                isinstance(h.formatter, JsonFormatter)
                for h in logger.handlers
                if not isinstance(h, logging.NullHandler)
            )
