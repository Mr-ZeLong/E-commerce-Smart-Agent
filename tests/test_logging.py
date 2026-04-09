import logging

import pytest

from app.core.logging import CorrelationIdFilter, correlation_id, set_correlation_id


class TestCorrelationIdFilter:
    def test_injects_correlation_id_into_record(self):
        filter_ = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        set_correlation_id("abc123")
        result = filter_.filter(record)

        assert result is True
        assert record.correlation_id == "abc123"

    def test_defaults_to_dash_when_no_correlation_id(self):
        filter_ = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        # Reset contextvar to default
        correlation_id.set(None)
        result = filter_.filter(record)

        assert result is True
        assert record.correlation_id == "-"


class TestSetCorrelationId:
    def test_sets_contextvar_value(self):
        set_correlation_id("ctx-value-42")
        assert correlation_id.get() == "ctx-value-42"

    def test_overwrites_existing_value(self):
        set_correlation_id("first")
        set_correlation_id("second")
        assert correlation_id.get() == "second"
