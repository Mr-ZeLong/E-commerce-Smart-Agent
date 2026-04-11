from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluation.metrics import (
    answer_correctness,
    intent_accuracy,
    rag_precision,
    slot_recall,
)
from app.evaluation.pipeline import EvaluationPipeline


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


def test_rag_precision_exact_match():
    chunks = ["退换货政策: 7天无理由", "其他信息"]
    assert rag_precision("退换货政策", chunks) == pytest.approx(1.0)


def test_rag_precision_token_match():
    chunks = ["关于发货时效的说明", "其他信息"]
    assert rag_precision("发货时效", chunks) == pytest.approx(1.0)


def test_rag_precision_no_match():
    chunks = ["不相关的内容", "其他信息"]
    assert rag_precision("退换货政策", chunks) == pytest.approx(0.0)


def test_rag_precision_empty_chunks():
    assert rag_precision("query", []) == 0.0


@pytest.mark.asyncio
async def test_answer_correctness_parses_score():
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="0.85")
    score = await answer_correctness("Q", "expected", "actual", mock_llm)
    assert score == pytest.approx(0.85)
    mock_llm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_answer_correctness_clamps_score():
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="1.5")
    score = await answer_correctness("Q", "expected", "actual", mock_llm)
    assert score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_answer_correctness_empty_actual():
    mock_llm = AsyncMock()
    score = await answer_correctness("Q", "expected", "", mock_llm)
    assert score == 0.0
    mock_llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_run(tmp_path):
    dataset_path = tmp_path / "golden_dataset.jsonl"
    dataset_path.write_text(
        '{"query": "查询订单SN20240001的状态", "expected_intent": "ORDER", '
        '"expected_slots": {"order_sn": "SN20240001"}, '
        '"expected_answer_fragment": "订单", "expected_audit_level": "auto"}\n'
        '{"query": "你们的退换货政策是什么", "expected_intent": "POLICY", '
        '"expected_slots": {}, "expected_answer_fragment": "退换货政策", '
        '"expected_audit_level": "auto"}\n',
        encoding="utf-8",
    )

    mock_intent_service = AsyncMock()
    mock_intent_service.recognize.side_effect = [
        MagicMock(
            primary_intent=MagicMock(value="ORDER"),
            slots={"order_sn": "SN20240001"},
        ),
        MagicMock(
            primary_intent=MagicMock(value="POLICY"),
            slots={},
        ),
    ]

    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = [
        {"answer": "订单已发货"},
        {
            "answer": "支持7天无理由退换货",
            "retrieval_result": {"chunks": ["退换货政策: 7天无理由"]},
        },
    ]

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="1.0")

    pipeline = EvaluationPipeline(
        intent_service=mock_intent_service,
        llm=mock_llm,
        graph=mock_graph,
    )

    results = await pipeline.run(str(dataset_path))

    assert results["intent_accuracy"] == pytest.approx(1.0)
    assert results["slot_recall"] == pytest.approx(1.0)
    assert results["rag_precision"] == pytest.approx(1.0)
    assert results["answer_correctness"] == pytest.approx(1.0)
    assert results["total_records"] == 2

    print("EVALUATION_METRICS:", results)

    assert mock_intent_service.recognize.await_count == 2
    assert mock_graph.ainvoke.await_count == 2
    assert mock_llm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_pipeline_run_graph_failure_graceful(tmp_path):
    dataset_path = tmp_path / "golden_dataset.jsonl"
    dataset_path.write_text(
        '{"query": "查询订单", "expected_intent": "ORDER", '
        '"expected_slots": {}, "expected_answer_fragment": "订单", '
        '"expected_audit_level": "auto"}\n',
        encoding="utf-8",
    )

    mock_intent_service = AsyncMock()
    mock_intent_service.recognize.return_value = MagicMock(
        primary_intent=MagicMock(value="ORDER"),
        slots={},
    )

    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = Exception("graph failure")

    mock_llm = AsyncMock()

    pipeline = EvaluationPipeline(
        intent_service=mock_intent_service,
        llm=mock_llm,
        graph=mock_graph,
    )

    results = await pipeline.run(str(dataset_path))

    assert results["intent_accuracy"] == pytest.approx(1.0)
    assert results["slot_recall"] == pytest.approx(0.0)
    assert results["rag_precision"] == 0.0
    assert results["answer_correctness"] == 0.0
    assert results["total_records"] == 1
