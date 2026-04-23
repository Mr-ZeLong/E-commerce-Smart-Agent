"""Base types for output content moderation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


def calculate_risk_level(score: float) -> Literal["low", "medium", "high"]:
    """Map a 0-1 risk score to a discrete risk level."""
    if score >= 0.7:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"


class LayerResult(BaseModel):
    """Result from a single moderation layer."""

    is_safe: bool
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"]
    reason: str | None = None
    details: dict | None = None


class ModerationResult(BaseModel):
    """Result of content moderation across all layers."""

    is_safe: bool
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"]
    blocked_by_layer: int | None = None
    replacement_text: str | None = None
    reason: str
    layer_results: dict[str, LayerResult] = Field(default_factory=dict)
