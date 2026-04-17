"""Observation masking utilities for context optimization."""

from typing import Any

from app.core.config import settings


def mask_observation(data: dict[str, Any], max_chars: int | None = None) -> dict[str, Any]:
    """Mask dictionary values whose string representation exceeds ``max_chars``."""
    if max_chars is None:
        max_chars = getattr(settings, "OBSERVATION_MASKING_MAX_CHARS", 500)

    result: dict[str, Any] = {}
    for key, value in data.items():
        text = str(value)
        if len(text) > max_chars:
            result[key] = {
                "_masked": True,
                "summary": text[:200].replace("\n", " ") + "...",
                "reference_id": key,
                "original_length": len(text),
            }
        else:
            result[key] = value
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
