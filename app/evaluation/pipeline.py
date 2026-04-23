"""Core evaluation pipeline for the Golden Dataset."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.tracing import build_llm_config
from app.evaluation.containment import containment_rate
from app.evaluation.metrics import (
    answer_correctness,
    intent_accuracy,
    rag_precision,
    slot_recall,
    token_efficiency,
)
from app.evaluation.tone_consistency import tone_consistency
from app.intent.service import IntentRecognitionService
from app.models.observability import GraphExecutionLog
from app.models.state import make_agent_state
from app.observability.latency_tracker import compute_node_latency_stats

logger = logging.getLogger(__name__)


class EvaluationPipeline:
    """Runs offline evaluation against a golden dataset."""

    def __init__(
        self,
        intent_service: IntentRecognitionService,
        llm: BaseChatModel,
        graph: Any,
        db_session: AsyncSession | None = None,
    ):
        self.intent_service = intent_service
        self.llm = llm
        self.graph = graph
        self.db_session = db_session

    async def run(self, golden_dataset_path: str) -> dict[str, Any]:
        """Load the golden dataset and compute evaluation metrics.

        Args:
            golden_dataset_path: Path to a JSONL file containing evaluation records.

        Returns:
             dict with ``intent_accuracy``, ``slot_recall``, ``rag_precision``,
             ``answer_correctness``, ``token_efficiency``, ``tone_consistency``,
             ``containment_rate``, ``latency_stats`` and ``total_records``.
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
        token_efficiencies: list[float] = []
        conversation_turns: list[dict[str, str]] = []

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
            config = build_llm_config(
                agent_name="evaluation_pipeline",
                tags=["evaluation", "internal"],
            )
            config = {**config, "configurable": {"thread_id": session_id}}
            try:
                final_state = await self.graph.ainvoke(initial_state, config=config)
            except (SQLAlchemyError, RuntimeError):
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

            context_tokens = final_state.get("context_tokens") or 0
            output_tokens = final_state.get("output_tokens") or len(actual_answer)
            if context_tokens > 0 and output_tokens >= 0:
                token_efficiencies.append(token_efficiency(context_tokens, output_tokens))

            conversation_turns.append({"role": "user", "content": query})
            conversation_turns.append({"role": "assistant", "content": actual_answer})

            logger.info(
                "Evaluated query='%s' intent=%s slots=%s",
                query,
                actual_intent,
                actual_slots,
            )

        tone_score = 0.0
        if conversation_turns:
            tone_score = await tone_consistency(conversation_turns, self.llm)

        results: dict[str, Any] = {
            "intent_accuracy": intent_accuracy(pred_intents, ref_intents),
            "slot_recall": slot_recall(pred_slots_list, ref_slots_list),
            "rag_precision": sum(rag_scores) / len(rag_scores) if rag_scores else 0.0,
            "answer_correctness": (
                sum(correctness_scores) / len(correctness_scores) if correctness_scores else 0.0
            ),
            "token_efficiency": (
                sum(token_efficiencies) / len(token_efficiencies) if token_efficiencies else 0.0
            ),
            "tone_consistency": tone_score,
            "total_records": len(records),
        }

        if self.db_session is not None:
            try:
                stmt = select(GraphExecutionLog)
                result = await self.db_session.exec(stmt)
                logs: list[GraphExecutionLog] = list(result.all())
                results["containment_rate"] = containment_rate(logs)
            except (SQLAlchemyError, OperationalError):
                logger.exception("Failed to query containment rate from database.")
                results["containment_rate"] = 0.0

            try:
                latency_stats = await compute_node_latency_stats(self.db_session)
                results["latency_stats"] = latency_stats
            except (SQLAlchemyError, OperationalError):
                logger.exception("Failed to compute latency statistics from database.")
                results["latency_stats"] = {}
        else:
            results["containment_rate"] = 0.0
            results["latency_stats"] = {}

        return results
