"""Structured JSON logging with OpenTelemetry trace context.

Provides ``JsonFormatter`` for production environments and a helper to configure
the Python logging stack with the appropriate formatter based on settings.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

from app.core.logging import CorrelationIdFilter


class JsonFormatter(logging.Formatter):
    """Emit log records as JSON lines with structured fields.

    Output schema (production)::

        {
            "timestamp": "2024-01-15T09:30:00.123456+00:00",
            "level": "ERROR",
            "logger": "app.api.v1.chat",
            "message": "Something went wrong",
            "trace_id": "abc...",
            "span_id": "def...",
            "correlation_id": "abc123",
            "source_file": "app/api/v1/chat.py",
            "line_number": 42,
            "stack_trace": "..."   // only for exceptions
        }
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format *record* as a single JSON line."""
        log_obj: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source_file": record.pathname,
            "line_number": record.lineno,
        }

        # Correlation ID from contextvar (set by CorrelationIdFilter or middleware)
        cid = getattr(record, "correlation_id", None)
        if cid and cid != "-":
            log_obj["correlation_id"] = cid

        # OpenTelemetry trace/span IDs
        span = trace.get_current_span()
        span_context = span.get_span_context()
        if span_context.is_valid:
            log_obj["trace_id"] = format(span_context.trace_id, "032x")
            log_obj["span_id"] = format(span_context.span_id, "016x")

        if record.exc_info and record.exc_info[0] is not None:
            log_obj["stack_trace"] = self.formatException(record.exc_info)
        elif record.levelno >= logging.WARNING and record.stack_info:
            log_obj["stack_trace"] = self.formatStack(record.stack_info)

        # Extra fields added by application code
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "exc_info",
                "exc_text",
                "stack_info",
                "correlation_id",
                "trace_id",
                "span_id",
                "message",
            }:
                log_obj[key] = value

        return json.dumps(log_obj, ensure_ascii=False, default=str)


class SafeTextFormatter(logging.Formatter):
    """Text formatter that guarantees ``correlation_id`` is present on records."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return super().format(record)


def configure_logging(*, log_format: str = "text") -> None:
    """Configure root logging with the chosen formatter.

    Args:
        log_format: ``"json"`` for ``JsonFormatter`` or ``"text"`` for
            ``SafeTextFormatter``.
    """
    if log_format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = SafeTextFormatter(
            "%(asctime)s [%(correlation_id)s] %(levelname)s %(name)s - %(message)s"
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Remove existing StreamHandlers to avoid duplicate output on re-configuration
    for h in root_logger.handlers[:]:
        if isinstance(h, logging.StreamHandler):
            root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    root_logger.addFilter(CorrelationIdFilter())

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        for h in uvicorn_logger.handlers[:]:
            if isinstance(h, logging.StreamHandler):
                uvicorn_logger.removeHandler(h)
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.addFilter(CorrelationIdFilter())
