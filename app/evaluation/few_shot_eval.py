"""Few-shot intent classification evaluation."""

from __future__ import annotations

import logging
import random
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from app.intent.classifier import IntentClassifier
from app.intent.few_shot_loader import load_intent_examples
from app.intent.models import IntentResult

logger = logging.getLogger(__name__)


def _result_to_dict(result: IntentResult) -> dict[str, Any]:
    return {
        "primary_intent": result.primary_intent.value,
        "secondary_intent": result.secondary_intent.value,
        "tertiary_intent": result.tertiary_intent,
        "confidence": result.confidence,
        "slots": result.slots,
    }


async def evaluate_intent_accuracy(
    llm: BaseChatModel,
    test_examples: list[dict[str, Any]] | None = None,
    use_few_shot: bool = True,
) -> dict[str, Any]:
    """Evaluate intent classification accuracy against a test set.

    If ``test_examples`` is not provided, uses 20%% of the loaded intent examples
    as a hold-out test set.
    """
    all_examples = load_intent_examples()
    if not all_examples:
        return {"accuracy": 0.0, "total": 0, "correct": 0, "use_few_shot": use_few_shot}

    if test_examples is None:
        random.seed(42)
        shuffled = all_examples[:]
        random.shuffle(shuffled)
        split_idx = max(1, int(len(shuffled) * 0.8))
        test_examples = shuffled[split_idx:]

    classifier = IntentClassifier(llm)
    if not use_few_shot:
        classifier._few_shot_examples = []

    correct = 0
    total = len(test_examples)
    errors: list[dict[str, Any]] = []

    for ex in test_examples:
        result = await classifier.classify(ex["query"])
        pred_primary = result.primary_intent.value if result.primary_intent else ""
        ref_primary = ex.get("primary_intent", "")
        if pred_primary == ref_primary:
            correct += 1
        else:
            errors.append(
                {
                    "query": ex["query"],
                    "expected": ref_primary,
                    "predicted": pred_primary,
                    "confidence": result.confidence,
                }
            )

    accuracy = round(correct / total, 4) if total > 0 else 0.0
    return {
        "accuracy": accuracy,
        "total": total,
        "correct": correct,
        "use_few_shot": use_few_shot,
        "errors": errors[:10],
    }


async def compare_few_shot_performance(llm: BaseChatModel) -> dict[str, Any]:
    """Compare intent accuracy with and without few-shot examples."""
    random.seed(42)
    all_examples = load_intent_examples()
    shuffled = all_examples[:]
    random.shuffle(shuffled)
    split_idx = max(1, int(len(shuffled) * 0.8))
    test_examples = shuffled[split_idx:]

    without_fs = await evaluate_intent_accuracy(llm, test_examples, use_few_shot=False)
    with_fs = await evaluate_intent_accuracy(llm, test_examples, use_few_shot=True)

    improvement = round(with_fs["accuracy"] - without_fs["accuracy"], 4)
    return {
        "without_few_shot": without_fs,
        "with_few_shot": with_fs,
        "improvement": improvement,
        "meets_target": improvement >= 0.03,
    }
