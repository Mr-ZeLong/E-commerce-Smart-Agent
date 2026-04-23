"""Output content moderation 4-layer architecture.

Provides a multi-layered safety system for filtering agent responses
before they reach users.
"""

from app.safety.embeddings import EmbeddingSimilarityLayer
from app.safety.llm_judge import LLMJudgeLayer
from app.safety.output_moderator import OutputModerator
from app.safety.patterns import RegexPatternLayer
from app.safety.rules import RuleBasedLayer
from app.safety.types import (
    LayerResult,
    ModerationResult,
    calculate_risk_level,
)

__all__ = [
    "calculate_risk_level",
    "LayerResult",
    "ModerationResult",
    "EmbeddingSimilarityLayer",
    "LLMJudgeLayer",
    "OutputModerator",
    "RegexPatternLayer",
    "RuleBasedLayer",
]
