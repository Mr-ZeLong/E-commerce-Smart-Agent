import contextvars
import logging
import uuid

correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or "-"
        return True


def set_correlation_id(cid: str) -> None:
    correlation_id.set(cid)


def generate_correlation_id() -> str:
    return uuid.uuid4().hex[:16]
