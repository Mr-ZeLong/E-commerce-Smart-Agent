"""Observation masking utilities for context optimization."""

from typing import Any

from app.context.pii_filter import PIIFilter, pii_filter
from app.core.config import settings


def mask_observation(
    data: dict[str, Any],
    max_chars: int | None = None,
    filter_pii: bool = True,
    pii_filter_instance: PIIFilter | None = None,
) -> dict[str, Any]:
    """Mask dictionary values whose string representation exceeds ``max_chars``.

    PII is redacted before length-based masking when ``filter_pii`` is True,
    following the masking priority rule: PII and secrets first.
    """
    if max_chars is None:
        max_chars = getattr(settings, "OBSERVATION_MASKING_MAX_CHARS", 500)

    pii = pii_filter_instance or pii_filter
    result: dict[str, Any] = {}
    for key, value in data.items():
        text = str(value)
        if filter_pii:
            text = pii.filter_text(text).redacted_text
        if len(text) > max_chars:
            result[key] = {
                "_masked": True,
                "summary": text[:200].replace("\n", " ") + "...",
                "reference_id": key,
                "original_length": len(text),
            }
        else:
            result[key] = text
    return result


def mask_context_parts(parts: list[str], max_chars: int | None = None) -> list[str]:
    """Mask individual context part strings that exceed ``max_chars``."""
    if max_chars is None:
        max_chars = getattr(settings, "OBSERVATION_MASKING_MAX_CHARS", 500)
    result: list[str] = []
    for part in parts:
        if len(part) > max_chars:
            result.append(
                f"{part[:200].replace(chr(10), ' ')}... [masked, original_length={len(part)}]"
            )
        else:
            result.append(part)
    return result
