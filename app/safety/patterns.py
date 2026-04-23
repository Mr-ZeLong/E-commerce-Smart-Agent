"""Regex pattern moderation layer (Layer 2) — injection and unsafe content.

Detects prompt injection attempts, code execution, and other unsafe
patterns in agent output using precompiled regex.
"""

from __future__ import annotations

import logging
import re

from app.safety.types import LayerResult, calculate_risk_level

logger = logging.getLogger(__name__)

# Precompiled injection patterns
_INJECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "ignore_instructions": re.compile(
        r"ignore\s+(?:previous|all|the)\s+(?:instructions?|prompts?)", re.IGNORECASE
    ),
    "dan_mode": re.compile(r"\bDAN\b"),
    "jailbreak": re.compile(r"jailbreak", re.IGNORECASE),
    "system_prompt": re.compile(r"system\s*[:\-]?\s*prompt", re.IGNORECASE),
}

# Unsafe code / script patterns
_CODE_PATTERNS: dict[str, re.Pattern[str]] = {
    "script_tag": re.compile(r"<script", re.IGNORECASE),
    "javascript_protocol": re.compile(r"javascript:", re.IGNORECASE),
    "onload_handler": re.compile(r"onload\s*=", re.IGNORECASE),
    "onerror_handler": re.compile(r"onerror\s*=", re.IGNORECASE),
}

# Patterns inherited from input safety — adapted for output
_UNSAFE_PATTERNS: dict[str, re.Pattern[str]] = {
    "exec_func": re.compile(r"exec\s*\(", re.IGNORECASE),
    "eval_func": re.compile(r"eval\s*\(", re.IGNORECASE),
    "import_stmt": re.compile(r"import\s+\w+", re.IGNORECASE),
}


class RegexPatternLayer:
    """Layer 2: Regex-based detection of injection and code patterns.

    Target latency: <5ms.
    """

    def __init__(
        self,
        injection_patterns: dict[str, re.Pattern[str]] | None = None,
        code_patterns: dict[str, re.Pattern[str]] | None = None,
        unsafe_patterns: dict[str, re.Pattern[str]] | None = None,
    ) -> None:
        """Initialize with optional custom pattern sets.

        Args:
            injection_patterns: Override default injection patterns.
            code_patterns: Override default code patterns.
            unsafe_patterns: Override default unsafe patterns.
        """
        self.injection_patterns = injection_patterns or _INJECTION_PATTERNS
        self.code_patterns = code_patterns or _CODE_PATTERNS
        self.unsafe_patterns = unsafe_patterns or _UNSAFE_PATTERNS

    def check(self, content: str) -> LayerResult:
        """Check content for injection attempts and unsafe patterns.

        Args:
            content: Text to check.

        Returns:
            LayerResult with risk assessment.
        """
        details: dict[str, list[str]] = {
            "injection": [],
            "code": [],
            "unsafe": [],
        }
        risk_score = 0.0

        # Check injection patterns
        for name, pattern in self.injection_patterns.items():
            if pattern.search(content):
                details["injection"].append(name)
                risk_score = max(risk_score, 0.9)

        # Check code patterns
        for name, pattern in self.code_patterns.items():
            if pattern.search(content):
                details["code"].append(name)
                risk_score = max(risk_score, 0.85)

        # Check unsafe patterns
        for name, pattern in self.unsafe_patterns.items():
            if pattern.search(content):
                details["unsafe"].append(name)
                risk_score = max(risk_score, 0.75)

        if risk_score > 0:
            logger.info(
                "RegexPatternLayer matched injection=%d, code=%d, unsafe=%d",
                len(details["injection"]),
                len(details["code"]),
                len(details["unsafe"]),
            )
            return LayerResult(
                is_safe=False,
                risk_score=risk_score,
                risk_level=calculate_risk_level(risk_score),
                reason=f"Detected injection/unsafe patterns: {details}",
                details=details,
            )

        return LayerResult(
            is_safe=True,
            risk_score=0.0,
            risk_level="low",
            reason="No injection or unsafe patterns detected",
        )
