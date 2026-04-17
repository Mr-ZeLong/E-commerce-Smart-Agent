"""Tests for shadow testing functionality."""

import pytest

from app.evaluation.shadow import (
    ShadowComparisonResult,
    ShadowOrchestrator,
    _answer_similarity,
)


def test_should_sample_deterministic():
    orchestrator = ShadowOrchestrator(sample_rate=0.1)
    results = {orchestrator.should_sample(f"thread_{i}") for i in range(1000)}
    assert True in results
    assert False in results


def test_should_sample_zero_rate():
    orchestrator = ShadowOrchestrator(sample_rate=0.0)
    assert orchestrator.should_sample("any_thread") is False


def test_should_sample_full_rate():
    orchestrator = ShadowOrchestrator(sample_rate=1.0)
    assert orchestrator.should_sample("any_thread") is True


def test_answer_similarity_identical():
    assert _answer_similarity("hello world", "hello world") == pytest.approx(1.0)


def test_answer_similarity_completely_different():
    assert _answer_similarity("abc", "xyz") == pytest.approx(0.0)


def test_answer_similarity_partial():
    score = _answer_similarity("hello world", "hello there")
    assert 0.0 < score < 1.0


def test_answer_similarity_empty_both():
    assert _answer_similarity("", "") == pytest.approx(1.0)


def test_answer_similarity_one_empty():
    assert _answer_similarity("hello", "") == pytest.approx(0.0)


def test_compare_results_match():
    prod_result = {
        "result": {"intent_category": "ORDER", "answer": "Your order is confirmed"},
        "latency_ms": 100,
    }
    shadow_result = {
        "result": {"intent_category": "ORDER", "answer": "Your order is confirmed"},
        "latency_ms": 120,
    }

    result = ShadowOrchestrator.compare_results("thread_1", prod_result, shadow_result)

    assert result.thread_id == "thread_1"
    assert result.production_intent == "ORDER"
    assert result.shadow_intent == "ORDER"
    assert result.intent_match is True
    assert result.production_answer == "Your order is confirmed"
    assert result.shadow_answer == "Your order is confirmed"
    assert result.answer_similarity == pytest.approx(1.0)
    assert result.production_latency_ms == 100
    assert result.shadow_latency_ms == 120
    assert result.latency_delta_ms == 20


def test_compare_results_mismatch():
    prod_result = {
        "result": {"intent_category": "ORDER", "answer": "Order confirmed"},
        "latency_ms": 100,
    }
    shadow_result = {
        "result": {"intent_category": "POLICY", "answer": "Policy details"},
        "latency_ms": 150,
    }

    result = ShadowOrchestrator.compare_results("thread_2", prod_result, shadow_result)

    assert result.intent_match is False
    assert result.production_intent == "ORDER"
    assert result.shadow_intent == "POLICY"
    assert result.latency_delta_ms == 50


def test_generate_report_empty():
    report = ShadowOrchestrator.generate_report([])
    assert report.total_comparisons == 0
    assert report.intent_match_rate == 0.0
    assert report.avg_answer_similarity == 0.0
    assert report.avg_latency_delta_ms == 0.0
    assert report.latency_regression is False


def test_generate_report_with_results():
    from datetime import UTC, datetime

    results = [
        ShadowComparisonResult(
            thread_id="t1",
            production_intent="ORDER",
            shadow_intent="ORDER",
            intent_match=True,
            production_answer="ans1",
            shadow_answer="ans1",
            answer_similarity=1.0,
            production_latency_ms=100,
            shadow_latency_ms=120,
            latency_delta_ms=20,
            timestamp=datetime.now(UTC),
        ),
        ShadowComparisonResult(
            thread_id="t2",
            production_intent="ORDER",
            shadow_intent="POLICY",
            intent_match=False,
            production_answer="ans2",
            shadow_answer="ans3",
            answer_similarity=0.5,
            production_latency_ms=100,
            shadow_latency_ms=700,
            latency_delta_ms=600,
            timestamp=datetime.now(UTC),
        ),
    ]

    report = ShadowOrchestrator.generate_report(results)

    assert report.total_comparisons == 2
    assert report.intent_match_rate == 0.5
    assert report.avg_answer_similarity == 0.75
    assert report.avg_latency_delta_ms == 310.0
    assert report.latency_regression is False


@pytest.mark.asyncio
async def test_run_shadow_mock_graphs():
    class MockGraph:
        def __init__(self, intent, answer):
            self.intent = intent
            self.answer = answer

        async def ainvoke(self, state, config=None):
            return {
                "intent_category": self.intent,
                "answer": self.answer,
            }

    prod_graph = MockGraph("ORDER", "Production answer")
    shadow_graph = MockGraph("ORDER", "Shadow answer")

    prod_result, shadow_result = await ShadowOrchestrator.run_shadow(
        "test query", prod_graph, shadow_graph
    )

    assert prod_result["result"]["intent_category"] == "ORDER"
    assert shadow_result["result"]["intent_category"] == "ORDER"
    assert prod_result["latency_ms"] >= 0
    assert shadow_result["latency_ms"] >= 0
