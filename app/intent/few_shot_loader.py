from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_INTENT_EXAMPLES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "prompt_examples" / "intent"
)

_COMPLAINT_EXAMPLES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "prompt_examples" / "complaint"
)


def _token_overlap_score(query: str, example_query: str) -> float:
    query_tokens = set(query.lower().split())
    example_tokens = set(example_query.lower().split())
    if not query_tokens or not example_tokens:
        return 0.0
    intersection = query_tokens & example_tokens
    return len(intersection) / max(len(query_tokens), len(example_tokens))


def _load_examples_from_dir(directory: Path) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    if not directory.exists():
        logger.warning("Examples directory not found: %s", directory)
        return examples

    for file_path in directory.glob("*.jsonl"):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        examples.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON line in %s: %s", file_path, line)
        except OSError:
            logger.warning("Failed to read examples file: %s", file_path)
    return examples


def load_intent_examples() -> list[dict[str, Any]]:
    return _load_examples_from_dir(_INTENT_EXAMPLES_DIR)


def load_complaint_examples() -> list[dict[str, Any]]:
    return _load_examples_from_dir(_COMPLAINT_EXAMPLES_DIR)


def select_top_k_examples(
    query: str, examples: list[dict[str, Any]], k: int = 3
) -> list[dict[str, Any]]:
    scored = [(_token_overlap_score(query, ex.get("query", "")), ex) for ex in examples]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ex for score, ex in scored[:k] if score > 0]


def format_intent_examples_for_prompt(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return ""
    parts = ["\n请参考以下示例进行意图识别:\n"]
    for idx, ex in enumerate(examples, 1):
        parts.append(f"示例 {idx}:")
        parts.append(f"  用户输入: {ex.get('query', '')}")
        parts.append(f"  意图: {ex.get('primary_intent', '')} / {ex.get('secondary_intent', '')}")
        if ex.get("tertiary_intent"):
            parts.append(f"  三级意图: {ex['tertiary_intent']}")
        slots = ex.get("slots", {})
        if slots:
            parts.append(f"  槽位: {slots}")
        if ex.get("reasoning"):
            parts.append(f"  推理: {ex['reasoning']}")
        parts.append("")
    return "\n".join(parts)


def format_complaint_examples_for_prompt(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return ""
    parts = ["\n请参考以下投诉处理示例:\n"]
    for idx, ex in enumerate(examples, 1):
        parts.append(f"示例 {idx}:")
        parts.append(f"  用户投诉: {ex.get('query', '')}")
        parts.append(f"  投诉类别: {ex.get('complaint_category', '')}")
        parts.append(f"  紧急程度: {ex.get('urgency', '')}")
        parts.append(f"  建议处理: {ex.get('expected_action', '')}")
        if ex.get("reasoning"):
            parts.append(f"  分析: {ex['reasoning']}")
        parts.append("")
    return "\n".join(parts)
