from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_INTENT_EXAMPLES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "prompt_examples" / "intent"
)

_COMPLAINT_EXAMPLES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "prompt_examples" / "complaint"
)

_AGENT_TYPES = {
    "order",
    "product",
    "cart",
    "payment",
    "logistics",
    "account",
    "policy",
    "complaint",
    "router",
}


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


def load_agent_examples(agent_type: str) -> list[dict[str, Any]]:
    """Load few-shot examples for a specific agent type.

    Args:
        agent_type: One of the supported agent types:
            order, product, cart, payment, logistics, account, policy, complaint, router

    Returns:
        List of example dictionaries.
    """
    agent_type = agent_type.lower().strip()
    if agent_type not in _AGENT_TYPES:
        logger.warning("Unknown agent type '%s', returning empty examples", agent_type)
        return []

    directory = (
        Path(__file__).resolve().parent.parent.parent / "data" / "prompt_examples" / agent_type
    )
    return _load_examples_from_dir(directory)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _semantic_select_top_k(
    query: str,
    examples: list[dict[str, Any]],
    k: int = 3,
) -> list[dict[str, Any]]:
    """Select top-k examples using semantic similarity via embeddings.

    Falls back to token overlap if embedding call fails or no embeddings available.
    """
    if not examples:
        return []

    try:
        from app.retrieval.embeddings import create_embedding_model

        embedding_model = create_embedding_model()
    except Exception as exc:
        logger.warning("Failed to create embedding model: %s", exc)
        return select_top_k_examples(query, examples, k=k)

    try:
        query_embedding = await embedding_model.aembed_query(query)
        example_texts = [ex.get("query", "") for ex in examples]
        example_embeddings = await embedding_model.aembed_documents(example_texts)

        scored = []
        for ex, emb in zip(examples, example_embeddings, strict=True):
            score = _cosine_similarity(query_embedding, emb)
            scored.append((score, ex))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ex for score, ex in scored[:k] if score > 0]
    except Exception as exc:
        logger.warning("Semantic selection failed, falling back to token overlap: %s", exc)
        return select_top_k_examples(query, examples, k=k)


def select_top_k_examples(
    query: str, examples: list[dict[str, Any]], k: int = 3
) -> list[dict[str, Any]]:
    scored = [(_token_overlap_score(query, ex.get("query", "")), ex) for ex in examples]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ex for score, ex in scored[:k] if score > 0]


async def select_top_k_examples_semantic(
    query: str,
    examples: list[dict[str, Any]],
    k: int = 3,
    use_semantic: bool = True,
) -> list[dict[str, Any]]:
    """Select top-k examples using semantic similarity or token overlap.

    Args:
        query: User query string.
        examples: List of example dictionaries.
        k: Number of examples to return.
        use_semantic: Whether to use semantic embeddings (True) or token overlap (False).

    Returns:
        List of top-k matching examples.
    """
    if use_semantic:
        return await _semantic_select_top_k(query, examples, k=k)
    return select_top_k_examples(query, examples, k=k)


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


def format_agent_examples_for_prompt(agent_type: str, examples: list[dict[str, Any]]) -> str:
    """Format few-shot examples for a specific agent type into a prompt string.

    Args:
        agent_type: The agent type (e.g., 'order', 'product', 'cart', etc.)
        examples: List of example dictionaries.

    Returns:
        Formatted prompt string with examples.
    """
    if not examples:
        return ""

    agent_type = agent_type.lower().strip()
    title_map = {
        "order": "订单处理",
        "product": "商品查询",
        "cart": "购物车操作",
        "payment": "支付查询",
        "logistics": "物流查询",
        "account": "账户管理",
        "policy": "政策咨询",
        "complaint": "投诉处理",
        "router": "意图路由",
    }
    title = title_map.get(agent_type, agent_type)
    parts = [f"\n请参考以下{title}示例:\n"]

    for idx, ex in enumerate(examples, 1):
        parts.append(f"示例 {idx}:")
        parts.append(f"  用户输入: {ex.get('query', '')}")

        intent = ex.get("expected_intent") or ex.get("primary_intent", "")
        action = ex.get("expected_action") or ex.get("secondary_intent", "")
        if intent:
            parts.append(f"  意图: {intent} / {action}")

        if ex.get("tertiary_intent"):
            parts.append(f"  三级意图: {ex['tertiary_intent']}")

        slots = ex.get("slots", {})
        if slots:
            parts.append(f"  槽位: {slots}")

        if ex.get("complaint_category"):
            parts.append(f"  投诉类别: {ex['complaint_category']}")
        if ex.get("urgency"):
            parts.append(f"  紧急程度: {ex['urgency']}")
        if ex.get("expected_action") and not action:
            parts.append(f"  建议处理: {ex['expected_action']}")

        if ex.get("reasoning"):
            parts.append(f"  推理: {ex['reasoning']}")
        parts.append("")

    return "\n".join(parts)
