import json

import pytest
from langgraph.graph import END, START, StateGraph

from app.evaluation.metrics import (
    answer_correctness,
    intent_accuracy,
    rag_precision,
    slot_recall,
)
from app.evaluation.pipeline import EvaluationPipeline
from app.intent.service import IntentRecognitionService
from app.models.state import AgentState


def test_intent_accuracy_full_match():
    preds = ["ORDER", "POLICY", "AFTER_SALES"]
    refs = ["ORDER", "POLICY", "AFTER_SALES"]
    assert intent_accuracy(preds, refs) == pytest.approx(1.0)


def test_intent_accuracy_partial_match():
    preds = ["ORDER", "POLICY", "AFTER_SALES"]
    refs = ["ORDER", "POLICY", "OTHER"]
    assert intent_accuracy(preds, refs) == pytest.approx(2 / 3)


def test_intent_accuracy_empty():
    assert intent_accuracy([], []) == 0.0


def test_slot_recall_full():
    preds = [{"order_sn": "SN1"}, {"a": 1, "b": 2}]
    refs = [{"order_sn": "SN1"}, {"a": 1}]
    assert slot_recall(preds, refs) == pytest.approx(1.0)


def test_slot_recall_partial():
    preds = [{"order_sn": "SN1"}, {"a": 1}]
    refs = [{"order_sn": "SN1", "phone": "138"}, {"a": 1, "b": 2}]
    assert slot_recall(preds, refs) == pytest.approx(0.5)


def test_slot_recall_skips_empty_refs():
    preds = [{}, {"order_sn": "SN1"}]
    refs = [{}, {"order_sn": "SN1"}]
    assert slot_recall(preds, refs) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_rag_precision_exact_match():
    chunks = ["退换货政策: 7天无理由", "其他信息"]
    assert await rag_precision("退换货政策", chunks) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_rag_precision_token_match():
    chunks = ["关于发货时效的说明", "其他信息"]
    assert await rag_precision("发货时效", chunks) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_rag_precision_no_match():
    chunks = ["不相关的内容", "其他信息"]
    assert await rag_precision("退换货政策", chunks) == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_rag_precision_empty_chunks():
    assert await rag_precision("query", []) == 0.0


@pytest.mark.asyncio
async def test_answer_correctness_parses_score(deterministic_llm):
    deterministic_llm.responses = [("correctness", "0.85")]
    score = await answer_correctness("Q", "expected", "actual", deterministic_llm)
    assert score == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_answer_correctness_clamps_score(deterministic_llm):
    deterministic_llm.responses = [("correctness", "1.5")]
    score = await answer_correctness("Q", "expected", "actual", deterministic_llm)
    assert score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_answer_correctness_empty_actual(deterministic_llm):
    score = await answer_correctness("Q", "expected", "", deterministic_llm)
    assert score == 0.0


def _build_success_graph():
    def _node(state: AgentState):
        return {
            "answer": "这是预期答案",
            "retrieval_result": {"chunks": ["政策A", "政策B"]},
        }

    workflow = StateGraph(AgentState)  # type: ignore
    workflow.add_node("policy_agent", _node)
    workflow.add_edge(START, "policy_agent")
    workflow.add_edge("policy_agent", END)
    return workflow.compile()


def _build_failing_graph():
    def _node(state: AgentState):
        raise Exception("graph failure")

    workflow = StateGraph(AgentState)  # type: ignore
    workflow.add_node("policy_agent", _node)
    workflow.add_edge(START, "policy_agent")
    workflow.add_edge("policy_agent", END)
    return workflow.compile()


async def _cleanup_intent_keys(redis_client):
    keys = []
    async for key in redis_client.scan_iter(match="intent:cache:*"):
        keys.append(key)
    async for key in redis_client.scan_iter(match="intent:session:*"):
        keys.append(key)
    if keys:
        await redis_client.delete(*keys)


@pytest.mark.asyncio
async def test_pipeline_run_full(tmp_path, deterministic_llm, redis_client):
    deterministic_llm.responses = [("correctness", "1.0")]

    dataset_path = tmp_path / "golden_dataset.jsonl"
    records = [
        {
            "query": "查订单状态",
            "expected_intent": "ORDER",
            "expected_slots": {},
            "expected_answer_fragment": "订单",
        },
        {
            "query": "退换货政策",
            "expected_intent": "POLICY",
            "expected_slots": {"matched_pattern": ""},
            "expected_answer_fragment": "预期",
        },
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8"
    )

    service = IntentRecognitionService(llm=deterministic_llm, redis_client=redis_client)
    pipeline = EvaluationPipeline(
        intent_service=service,
        llm=deterministic_llm,
        graph=_build_success_graph(),
    )

    results = await pipeline.run(str(dataset_path))

    assert results["intent_accuracy"] == pytest.approx(1.0)
    assert results["slot_recall"] == pytest.approx(1.0)
    assert results["rag_precision"] == pytest.approx(1.0)
    assert results["answer_correctness"] == pytest.approx(1.0)
    assert results["total_records"] == 2

    await _cleanup_intent_keys(redis_client)


@pytest.mark.asyncio
async def test_pipeline_run_graph_failure_graceful(tmp_path, deterministic_llm, redis_client):
    dataset_path = tmp_path / "golden_dataset.jsonl"
    record = {
        "query": "查订单",
        "expected_intent": "ORDER",
        "expected_slots": {},
        "expected_answer_fragment": "订单",
    }
    dataset_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    service = IntentRecognitionService(llm=deterministic_llm, redis_client=redis_client)
    pipeline = EvaluationPipeline(
        intent_service=service,
        llm=deterministic_llm,
        graph=_build_failing_graph(),
    )

    results = await pipeline.run(str(dataset_path))

    assert results["intent_accuracy"] == pytest.approx(1.0)
    assert results["slot_recall"] == pytest.approx(0.0)
    assert results["rag_precision"] == pytest.approx(0.0)
    assert results["answer_correctness"] == pytest.approx(0.0)
    assert results["total_records"] == 1

    await _cleanup_intent_keys(redis_client)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_answer_correctness(real_llm):
    score = await answer_correctness("运费怎么算？", "满100元免运费", "满100元免运费", real_llm)
    assert 0.0 <= score <= 1.0


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_answer_correctness_low(real_llm):
    score = await answer_correctness("运费怎么算？", "满100元免运费", "满50元免运费", real_llm)
    assert 0.0 <= score <= 1.0
