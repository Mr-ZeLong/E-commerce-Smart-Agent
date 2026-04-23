"""Alert models for the E-commerce Smart Agent.

Defines database entities for alert rules, events, and notifications.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class AlertSeverity(str, Enum):
    """Alert severity levels with SLA requirements."""

    P0 = "P0"  # Critical - immediate response (15 min)
    P1 = "P1"  # Warning - response within 1 hour
    P2 = "P2"  # Info - response within 4 hours


class AlertStatus(str, Enum):
    """Lifecycle status of an alert event."""

    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertRuleStatus(str, Enum):
    """Operational status of an alert rule."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class AlertChannel(str, Enum):
    """Supported notification channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"


class AlertRule(SQLModel, table=True):
    """Configurable alert rule definition."""

    __tablename__ = "alert_rules"

    id: int | None = Field(default=None, primary_key=True)

    # Rule identification
    name: str = Field(index=True, max_length=100, description="Alert rule name.")
    description: str | None = Field(default=None, max_length=500, description="Rule description.")

    # Rule configuration
    metric: str = Field(max_length=50, description="Metric to monitor (e.g., latency, error_rate).")
    operator: str = Field(max_length=10, description="Comparison operator (gt, lt, gte, lte, eq).")
    threshold: float = Field(description="Threshold value for the alert.")
    duration_seconds: int = Field(
        default=60, description="Duration the condition must persist before firing."
    )

    # Severity and status
    severity: AlertSeverity = Field(default=AlertSeverity.P2, description="Alert severity level.")
    status: AlertRuleStatus = Field(
        default=AlertRuleStatus.ENABLED, description="Rule operational status."
    )

    # Notification channels (JSON array of channel configs)
    channels: str = Field(
        default="[]", max_length=2000, description="JSON array of channel configurations."
    )

    # Deduplication / suppression
    suppress_interval_seconds: int = Field(
        default=300, description="Minimum seconds between repeated alerts."
    )
    auto_resolve: bool = Field(default=True, description="Auto-resolve when condition clears.")

    # Timestamps
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
    )


class AlertEvent(SQLModel, table=True):
    """Individual alert event (firing or resolved)."""

    __tablename__ = "alert_events"

    id: int | None = Field(default=None, primary_key=True)

    # Relationship to rule
    rule_id: int | None = Field(default=None, foreign_key="alert_rules.id", index=True)

    # Event details
    name: str = Field(max_length=100, description="Alert name at time of firing.")
    severity: AlertSeverity = Field(description="Severity at time of firing.")
    status: AlertStatus = Field(default=AlertStatus.FIRING, description="Current alert status.")
    message: str = Field(max_length=1000, description="Human-readable alert message.")
    metric_value: float | None = Field(
        default=None, description="Actual metric value that triggered the alert."
    )
    threshold: float | None = Field(default=None, description="Threshold value at time of firing.")

    # Context
    metadata_json: str | None = Field(
        default=None, max_length=2000, description="JSON metadata for the event."
    )

    # Lifecycle tracking
    fired_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    acknowledged_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    acknowledged_by: int | None = Field(default=None, description="User ID who acknowledged.")
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    resolved_by: int | None = Field(default=None, description="User ID who resolved.")
    resolution_reason: str | None = Field(
        default=None, max_length=500, description="Resolution reason."
    )


class AlertNotification(SQLModel, table=True):
    """Record of notification delivery attempts."""

    __tablename__ = "alert_notifications"

    id: int | None = Field(default=None, primary_key=True)

    # Relationship
    alert_event_id: int = Field(foreign_key="alert_events.id", index=True)

    # Channel info
    channel: AlertChannel = Field(description="Notification channel used.")
    destination: str = Field(
        max_length=500, description="Destination address (email, webhook URL, etc.)."
    )

    # Delivery status
    sent_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    success: bool = Field(
        default=False, description="Whether the notification was delivered successfully."
    )
    response_status: int | None = Field(default=None, description="HTTP status or error code.")
    response_body: str | None = Field(
        default=None, max_length=2000, description="Response body or error message."
    )
