import json
import logging
import sys
from unittest.mock import MagicMock, patch

from app.core.logging import CorrelationIdFilter
from app.core.structured_logging import (
    JsonFormatter,
    SafeTextFormatter,
    configure_logging,
)


class _CaptureHandler(logging.Handler):
    """Capture log records for assertions."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestJsonFormatter:
    def test_basic_fields_present(self):
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
        output = formatter.format(record)
        data = json.loads(output)

        assert "timestamp" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "hello world"
        assert data["source_file"] == "/path/to/test.py"
        assert data["line_number"] == 42

    def test_correlation_id_included(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc123"
        output = formatter.format(record)
        data = json.loads(output)

        assert data["correlation_id"] == "abc123"

    def test_correlation_id_omitted_when_dash(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "-"
        output = formatter.format(record)
        data = json.loads(output)

        assert "correlation_id" not in data

    def test_trace_and_span_ids_included(self):
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0xABC123
        mock_span_context.span_id = 0xDEF456

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        formatter = JsonFormatter()
        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="msg",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)

        data = json.loads(output)
        assert data["trace_id"] == "00000000000000000000000000abc123"
        assert data["span_id"] == "0000000000def456"

    def test_trace_and_span_ids_omitted_when_invalid(self):
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        formatter = JsonFormatter()
        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="msg",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)

        data = json.loads(output)
        assert "trace_id" not in data
        assert "span_id" not in data

    def test_exception_stack_trace_for_error(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("something broke")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="error msg",
                args=(),
                exc_info=exc_info,
            )
            output = formatter.format(record)

        data = json.loads(output)
        assert "stack_trace" in data
        assert "ValueError" in data["stack_trace"]
        assert "something broke" in data["stack_trace"]

    def test_stack_trace_for_warning_with_stack_info(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="warning msg",
            args=(),
            exc_info=None,
        )
        record.stack_info = "Stack (most recent call last):\n  File ..."
        output = formatter.format(record)

        data = json.loads(output)
        assert "stack_trace" in data
        assert "Stack (most recent call last)" in data["stack_trace"]

    def test_no_stack_trace_for_info(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="info msg",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)

        data = json.loads(output)
        assert "stack_trace" not in data

    def test_extra_fields_included(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"
        record.user_id = 42
        output = formatter.format(record)

        data = json.loads(output)
        assert data["custom_field"] == "custom_value"
        assert data["user_id"] == 42

    def test_invalid_json_values_serialized(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        record.unserializable = object()
        output = formatter.format(record)

        data = json.loads(output)
        assert "unserializable" in data


class TestSafeTextFormatter:
    def test_adds_correlation_id_when_missing(self):
        formatter = SafeTextFormatter("%(correlation_id)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert output == "- - hello"

    def test_preserves_existing_correlation_id(self):
        formatter = SafeTextFormatter("%(correlation_id)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc123"
        output = formatter.format(record)
        assert output == "abc123 - hello"


class TestConfigureLogging:
    def test_configures_json_format(self):
        configure_logging(log_format="json")
        root = logging.getLogger()
        assert len(root.handlers) >= 1
        handler = root.handlers[-1]
        assert isinstance(handler.formatter, JsonFormatter)

    def test_configures_text_format(self):
        configure_logging(log_format="text")
        root = logging.getLogger()
        assert len(root.handlers) >= 1
        handler = root.handlers[-1]
        assert isinstance(handler.formatter, SafeTextFormatter)

    def test_removes_duplicate_stream_handlers(self):
        configure_logging(log_format="json")
        configure_logging(log_format="json")
        root = logging.getLogger()
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 1

    def test_adds_correlation_id_filter(self):
        configure_logging(log_format="json")
        root = logging.getLogger()
        filter_types = [type(f) for f in root.filters]
        assert CorrelationIdFilter in filter_types

    def test_uvicorn_loggers_configured(self):
        configure_logging(log_format="json")
        for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
            logger = logging.getLogger(name)
            assert any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers)

    def test_logs_are_valid_json(self):
        configure_logging(log_format="json")
        logger = logging.getLogger("test.json.output")
        handler = _CaptureHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            logger.info("test message", extra={"request_id": "req-123"})
            assert len(handler.records) == 1
            output = handler.format(handler.records[0])
            data = json.loads(output)
            assert data["message"] == "test message"
            assert data["request_id"] == "req-123"
        finally:
            logger.removeHandler(handler)
