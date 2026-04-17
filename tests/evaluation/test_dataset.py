import json

import pytest
from langgraph.graph import END, START, StateGraph

from app.evaluation.dataset import (
    GoldenDataset,
    GoldenRecord,
    load_golden_dataset,
    validate_dataset_dimensions,
)
from app.evaluation.pipeline import EvaluationPipeline
from app.intent.service import IntentRecognitionService
from app.models.state import AgentState


def test_golden_record_valid():
    record = GoldenRecord(
        query="test query",
        expected_intent="ORDER",
        expected_slots={"order_sn": "SN1"},
        expected_answer_fragment="test",
        expected_audit_level="auto",
        dimension="order_query",
    )
    assert record.query == "test query"
    assert record.expected_intent == "ORDER"


def test_golden_record_invalid_intent():
    with pytest.raises(ValueError, match="Invalid intent"):
        GoldenRecord(
            query="test",
            expected_intent="INVALID_INTENT",
            expected_slots={},
            expected_answer_fragment="",
            expected_audit_level="auto",
            dimension="test",
        )


def test_golden_record_invalid_audit_level():
    with pytest.raises(ValueError, match="audit"):
        GoldenRecord(
            query="test",
            expected_intent="ORDER",
            expected_slots={},
            expected_answer_fragment="",
            expected_audit_level="invalid",
            dimension="test",
        )


def test_golden_record_empty_query():
    with pytest.raises(ValueError):
        GoldenRecord(
            query="",
            expected_intent="ORDER",
            expected_slots={},
            expected_answer_fragment="",
            expected_audit_level="auto",
            dimension="test",
        )


def test_load_golden_dataset_success(tmp_path):
    dataset_path = tmp_path / "test_dataset.jsonl"
    records = [
        {
            "query": "query one",
            "expected_intent": "ORDER",
            "expected_slots": {},
            "expected_answer_fragment": "order",
            "expected_audit_level": "auto",
            "dimension": "order_query",
        },
        {
            "query": "query two",
            "expected_intent": "POLICY",
            "expected_slots": {},
            "expected_answer_fragment": "policy",
            "expected_audit_level": "medium",
            "dimension": "policy_inquiry",
        },
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8"
    )

    dataset = load_golden_dataset(dataset_path)
    assert dataset.total_records == 2
    assert dataset.source_path == str(dataset_path)
    assert dataset.records[0].query == "query one"
    assert dataset.records[1].expected_intent == "POLICY"


def test_load_golden_dataset_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_golden_dataset("/nonexistent/path/dataset.jsonl")


def test_load_golden_dataset_invalid_json(tmp_path):
    dataset_path = tmp_path / "bad_dataset.jsonl"
    dataset_path.write_text("this is not json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_golden_dataset(dataset_path)


def test_load_golden_dataset_invalid_record(tmp_path):
    dataset_path = tmp_path / "bad_dataset.jsonl"
    bad_record = {
        "query": "test",
        "expected_intent": "BAD_INTENT",
        "expected_slots": {},
        "expected_answer_fragment": "",
        "expected_audit_level": "auto",
        "dimension": "test",
    }
    dataset_path.write_text(json.dumps(bad_record, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Validation failed"):
        load_golden_dataset(dataset_path)


def test_load_golden_dataset_skips_empty_lines(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "query": "q1",
                "expected_intent": "ORDER",
                "expected_slots": {},
                "expected_answer_fragment": "",
                "expected_audit_level": "auto",
                "dimension": "d1",
            },
            ensure_ascii=False,
        )
        + "\n\n\n",
        encoding="utf-8",
    )

    dataset = load_golden_dataset(dataset_path)
    assert dataset.total_records == 1


def test_dimension_counts():
    records = [
        GoldenRecord(
            query="q1", expected_intent="ORDER", expected_audit_level="auto", dimension="d1"
        ),
        GoldenRecord(
            query="q2", expected_intent="ORDER", expected_audit_level="auto", dimension="d1"
        ),
        GoldenRecord(
            query="q3", expected_intent="POLICY", expected_audit_level="auto", dimension="d2"
        ),
    ]
    dataset = GoldenDataset(records=records)
    assert dataset.dimension_counts == {"d1": 2, "d2": 1}


def test_filter_by_dimension():
    records = [
        GoldenRecord(
            query="q1", expected_intent="ORDER", expected_audit_level="auto", dimension="d1"
        ),
        GoldenRecord(
            query="q2", expected_intent="POLICY", expected_audit_level="auto", dimension="d2"
        ),
    ]
    dataset = GoldenDataset(records=records)
    filtered = dataset.filter_by_dimension("d1")
    assert len(filtered) == 1
    assert filtered[0].query == "q1"


def test_filter_by_intent():
    records = [
        GoldenRecord(
            query="q1", expected_intent="ORDER", expected_audit_level="auto", dimension="d1"
        ),
        GoldenRecord(
            query="q2", expected_intent="POLICY", expected_audit_level="auto", dimension="d2"
        ),
    ]
    dataset = GoldenDataset(records=records)
    filtered = dataset.filter_by_intent("ORDER")
    assert len(filtered) == 1
    assert filtered[0].query == "q1"


def test_validate_dataset_dimensions_pass():
    records = []
    for _ in range(30):
        records.append(
            GoldenRecord(
                query="q",
                expected_intent="ORDER",
                expected_audit_level="auto",
                dimension="order_query",
            )
        )
    for _ in range(25):
        records.append(
            GoldenRecord(
                query="q",
                expected_intent="AFTER_SALES",
                expected_audit_level="auto",
                dimension="refund_apply",
            )
        )

    dataset = GoldenDataset(records=records)
    result = validate_dataset_dimensions(dataset)
    assert result["valid"] is False
    assert result["details"]["order_query"]["valid"] is True
    assert result["details"]["refund_apply"]["valid"] is True


def test_validate_dataset_dimensions_custom_expectations():
    records = [
        GoldenRecord(
            query="q1", expected_intent="ORDER", expected_audit_level="auto", dimension="custom"
        ),
        GoldenRecord(
            query="q2", expected_intent="ORDER", expected_audit_level="auto", dimension="custom"
        ),
    ]
    dataset = GoldenDataset(records=records)
    result = validate_dataset_dimensions(dataset, expected_dimensions={"custom": 2})
    assert result["valid"] is True
    assert result["details"]["custom"]["actual"] == 2


def test_all_intents_valid():
    valid_intents = [
        "ORDER",
        "AFTER_SALES",
        "POLICY",
        "ACCOUNT",
        "PROMOTION",
        "PAYMENT",
        "LOGISTICS",
        "PRODUCT",
        "CART",
        "COMPLAINT",
        "OTHER",
    ]
    for intent in valid_intents:
        record = GoldenRecord(
            query="test",
            expected_intent=intent,
            expected_slots={},
            expected_answer_fragment="",
            expected_audit_level="auto",
            dimension="test",
        )
        assert record.expected_intent == intent


def test_golden_dataset_v2_loads():
    dataset = load_golden_dataset("data/golden_dataset_v2.jsonl")
    assert dataset.total_records == 160
    assert dataset.source_path == "data/golden_dataset_v2.jsonl"

    expected_counts = {
        "order_query": 30,
        "refund_apply": 25,
        "policy_inquiry": 25,
        "product_query": 20,
        "ambiguous_intent": 20,
        "multi_intent": 15,
        "abnormal_input": 15,
        "long_conversation": 10,
    }

    for dim, expected_count in expected_counts.items():
        actual_count = dataset.dimension_counts.get(dim, 0)
        assert actual_count == expected_count, (
            f"Dimension {dim}: expected {expected_count}, got {actual_count}"
        )


def test_golden_dataset_v2_intent_distribution():
    dataset = load_golden_dataset("data/golden_dataset_v2.jsonl")
    intent_counts: dict[str, int] = {}
    for record in dataset.records:
        intent = record.expected_intent
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    assert intent_counts.get("ORDER", 0) > 0
    assert intent_counts.get("AFTER_SALES", 0) > 0
    assert intent_counts.get("POLICY", 0) > 0
    assert intent_counts.get("PRODUCT", 0) > 0
    assert intent_counts.get("OTHER", 0) > 0


def test_golden_dataset_v2_audit_levels():
    dataset = load_golden_dataset("data/golden_dataset_v2.jsonl")
    audit_counts = {"auto": 0, "medium": 0, "manual": 0}
    for record in dataset.records:
        audit_counts[record.expected_audit_level] += 1

    assert audit_counts["auto"] > 0
    assert audit_counts["medium"] > 0
    assert audit_counts["manual"] > 0


def test_golden_dataset_v2_has_dimension_field():
    dataset = load_golden_dataset("data/golden_dataset_v2.jsonl")
    for record in dataset.records:
        assert record.dimension
        assert record.dimension in {
            "order_query",
            "refund_apply",
            "policy_inquiry",
            "product_query",
            "ambiguous_intent",
            "multi_intent",
            "abnormal_input",
            "long_conversation",
        }


def _build_eval_graph():
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


async def _cleanup_intent_keys(redis_client):
    keys = []
    async for key in redis_client.scan_iter(match="intent:cache:*"):
        keys.append(key)
    async for key in redis_client.scan_iter(match="intent:session:*"):
        keys.append(key)
    if keys:
        await redis_client.delete(*keys)


@pytest.mark.asyncio
async def test_dataset_v2_pipeline_dry_run(deterministic_llm, redis_client):
    deterministic_llm.responses = [("correctness", "1.0")]
    deterministic_llm.structured = {
        "SafetyCheckResult": {
            "is_safe": True,
            "risk_level": "low",
            "risk_type": None,
            "reason": "safe",
        }
    }

    service = IntentRecognitionService(llm=deterministic_llm, redis_client=redis_client)
    pipeline = EvaluationPipeline(
        intent_service=service,
        llm=deterministic_llm,
        graph=_build_eval_graph(),
    )

    results = await pipeline.run("data/golden_dataset_v2.jsonl")

    assert results["total_records"] == 160
    assert "intent_accuracy" in results
    assert "slot_recall" in results
    assert "rag_precision" in results
    assert "answer_correctness" in results

    await _cleanup_intent_keys(redis_client)
