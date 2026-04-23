"""PII audit log model for GDPR compliance and detection tracking.

Records when and where PII was detected and redacted, without storing
the actual PII values.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Integer, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class PIIAuditLog(SQLModel, table=True):
    """Audit log for PII detection events.

    Tracks *that* PII was detected and redacted, but never stores the
    actual sensitive values.
    """

    __tablename__ = "pii_audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None, index=True, description="User associated with the detected PII"
    )
    thread_id: str | None = Field(
        default=None, index=True, max_length=128, description="Conversation thread ID"
    )
    source: str = Field(
        max_length=64, description="Source of the text (e.g. chat_input, vector_memory)"
    )
    detection_types: dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
        description="Mapping of PII type to count of redactions",
    )
    redaction_count: int = Field(
        default=0, sa_column=Column(Integer, nullable=False), description="Total redactions"
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
