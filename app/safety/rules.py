"""Rule-based moderation layer (Layer 1) — PII and sensitive keywords.

Detects personally identifiable information and sensitive keywords
using precompiled regex patterns.
"""

from __future__ import annotations

import logging
import re

from app.safety.types import LayerResult, calculate_risk_level

logger = logging.getLogger(__name__)

# Precompile PII patterns for performance (<10ms target)
_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "credit_card": re.compile(r"\b\d{16,19}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\b1[3-9]\d{9}\b"),
}

# Case-insensitive keyword patterns
_SENSITIVE_KEYWORDS: list[str] = [
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private key",
    "secret key",
]


class RuleBasedLayer:
    """Layer 1: Fast rule-based detection of PII and sensitive terms.

    Target latency: <10ms.
    """

    def __init__(self, keywords: list[str] | None = None) -> None:
        """Initialize with optional custom keyword list.

        Args:
            keywords: Override default sensitive keywords.
        """
        self.keywords = keywords or _SENSITIVE_KEYWORDS

    def check(self, content: str) -> LayerResult:
        """Check content for PII and sensitive keywords.

        Args:
            content: Text to check.

        Returns:
            LayerResult with risk assessment.
        """
        details: dict[str, list[str]] = {"matched_patterns": [], "matched_keywords": []}
        risk_score = 0.0

        # Check PII patterns
        for name, pattern in _PII_PATTERNS.items():
            if pattern.search(content):
                details["matched_patterns"].append(name)
                if name == "credit_card":
                    risk_score = max(risk_score, 0.95)
                elif name == "ssn":
                    risk_score = max(risk_score, 0.9)
                elif name == "phone":
                    risk_score = max(risk_score, 0.7)

        # Check sensitive keywords
        content_lower = content.lower()
        for keyword in self.keywords:
            if keyword.lower() in content_lower:
                details["matched_keywords"].append(keyword)
                risk_score = max(risk_score, 0.8)

        if risk_score > 0:
            logger.info(
                "RuleBasedLayer matched %d patterns, %d keywords",
                len(details["matched_patterns"]),
                len(details["matched_keywords"]),
            )
            return LayerResult(
                is_safe=False,
                risk_score=risk_score,
                risk_level=calculate_risk_level(risk_score),
                reason=f"Detected PII/sensitive terms: {details}",
                details=details,
            )

        return LayerResult(
            is_safe=True,
            risk_score=0.0,
            risk_level="low",
            reason="No PII or sensitive keywords detected",
        )
