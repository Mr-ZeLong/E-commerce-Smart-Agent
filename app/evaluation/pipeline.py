"""Core evaluation pipeline for the Golden Dataset."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from app.evaluation.metrics import (
    answer_correctness,
    intent_accuracy,
    rag_precision,
    slot_recall,
)
from app.intent.service import IntentRecognitionService
from app.models.state import make_agent_state

logger = logging.getLogger(__name__)


class EvaluationPipeline:
    """Runs offline evaluation against a golden dataset."""

    def __init__(
        self,
        intent_service: IntentRecognitionService,
        llm: BaseChatModel,
        graph: Any,
    ):
        self.intent_service = intent_service
        self.llm = llm
        self.graph = graph

    async def run(self, golden_dataset_path: str) -> dict[str, Any]:
        """Load the golden dataset and compute evaluation metrics.

        Args:
            golden_dataset_path: Path to a JSONL file containing evaluation records.

        Returns:
             dict with ``intent_accuracy``, ``slot_recall``, ``rag_precision``,
             ``answer_correctness`` and ``total_records``.
        """
        path = Path(golden_dataset_path)
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))

        pred_intents: list[str] = []
        ref_intents: list[str] = []
        pred_slots_list: list[dict[str, Any]] = []
        ref_slots_list: list[dict[str, Any]] = []
        rag_scores: list[float] = []
        correctness_scores: list[float] = []

        for record in records:
            query = record["query"]
            expected_intent = record["expected_intent"]
            expected_slots = record.get("expected_slots") or {}
            expected_answer_fragment = record.get("expected_answer_fragment", "")

            session_id = f"eval-{uuid.uuid4().hex[:8]}"

            intent_result = await self.intent_service.recognize(
                query=query,
                session_id=session_id,
                conversation_history=None,
            )
            actual_intent = intent_result.primary_intent.value
            actual_slots = intent_result.slots or {}

            pred_intents.append(actual_intent)
            ref_intents.append(expected_intent)
            pred_slots_list.append(actual_slots)
            ref_slots_list.append(expected_slots)

            initial_state = make_agent_state(
                question=query,
                user_id=1,
                thread_id=session_id,
            )
            config = {"configurable": {"thread_id": session_id}}
            try:
                final_state = await self.graph.ainvoke(initial_state, config)
            except Exception:
                logger.exception("Graph invocation failed for query: %s", query)
                final_state = {}

            actual_answer = final_state.get("answer", "")

            if expected_intent == "POLICY":
                retrieval_result = final_state.get("retrieval_result") or {}
                chunks = retrieval_result.get("chunks", [])
                rag_scores.append(await rag_precision(query, chunks))

            if expected_answer_fragment and actual_answer:
                score = await answer_correctness(
                    question=query,
                    expected=expected_answer_fragment,
                    actual=actual_answer,
                    llm=self.llm,
                )
                correctness_scores.append(score)

            logger.info(
                "Evaluated query='%s' intent=%s slots=%s",
                query,
                actual_intent,
                actual_slots,
            )

        results: dict[str, Any] = {
            "intent_accuracy": intent_accuracy(pred_intents, ref_intents),
            "slot_recall": slot_recall(pred_slots_list, ref_slots_list),
            "rag_precision": sum(rag_scores) / len(rag_scores) if rag_scores else 0.0,
            "answer_correctness": (
                sum(correctness_scores) / len(correctness_scores) if correctness_scores else 0.0
            ),
            "total_records": len(records),
        }
        return results
