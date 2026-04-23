"""Tests for few_shot_loader module."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.intent.few_shot_loader import (
    _cosine_similarity,
    _token_overlap_score,
    format_agent_examples_for_prompt,
    format_complaint_examples_for_prompt,
    format_intent_examples_for_prompt,
    load_agent_examples,
    load_complaint_examples,
    load_intent_examples,
    select_top_k_examples,
    select_top_k_examples_semantic,
)

# ========== Directory and Loading Tests ==========


class TestLoadAgentExamples:
    def test_load_intent_examples_returns_list(self):
        examples = load_intent_examples()
        assert isinstance(examples, list)
        if examples:
            assert "query" in examples[0]
            assert "primary_intent" in examples[0]

    def test_load_complaint_examples_returns_list(self):
        examples = load_complaint_examples()
        assert isinstance(examples, list)
        if examples:
            assert "query" in examples[0]
            has_category = "complaint_category" in examples[0] or "complaint_category" in examples[
                0
            ].get("slots", {})
            assert has_category

    def test_load_agent_examples_all_types(self):
        for agent_type in [
            "order",
            "product",
            "cart",
            "payment",
            "logistics",
            "account",
            "policy",
            "complaint",
            "router",
        ]:
            examples = load_agent_examples(agent_type)
            assert isinstance(examples, list)
            assert len(examples) >= 0, f"Expected examples for {agent_type}"
            if examples:
                assert "query" in examples[0]
                has_intent = (
                    "expected_intent" in examples[0]
                    or "primary_intent" in examples[0]
                    or "complaint_category" in examples[0]
                )
                assert has_intent

    def test_load_agent_examples_unknown_type_returns_empty(self):
        examples = load_agent_examples("nonexistent_agent")
        assert examples == []

    def test_load_agent_examples_case_insensitive(self):
        examples_upper = load_agent_examples("ORDER")
        examples_lower = load_agent_examples("order")
        assert examples_upper == examples_lower

    def test_load_agent_examples_min_count(self):
        for agent_type in [
            "order",
            "product",
            "cart",
            "payment",
            "logistics",
            "account",
            "policy",
            "complaint",
            "router",
        ]:
            examples = load_agent_examples(agent_type)
            assert len(examples) >= 50, (
                f"Expected at least 50 examples for {agent_type}, got {len(examples)}"
            )


# ========== Token Overlap Tests ==========


class TestTokenOverlapScore:
    def test_exact_match(self):
        score = _token_overlap_score("查询订单状态", "查询订单状态")
        assert score == 1.0

    def test_partial_overlap(self):
        score = _token_overlap_score("query order status", "query order detail")
        assert 0.0 < score < 1.0

    def test_no_overlap(self):
        score = _token_overlap_score("abcdef", "ghijkl")
        assert score == 0.0

    def test_empty_query(self):
        score = _token_overlap_score("", "查询订单")
        assert score == 0.0

    def test_empty_example(self):
        score = _token_overlap_score("查询订单", "")
        assert score == 0.0

    def test_case_insensitive(self):
        score1 = _token_overlap_score("Query Order", "query order")
        score2 = _token_overlap_score("query order", "query order")
        assert score1 == score2


# ========== Cosine Similarity Tests ==========


class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        assert _cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        assert _cosine_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_zero_vector(self):
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        assert _cosine_similarity(vec1, vec2) == 0.0

    def test_different_dimensions(self):
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        assert _cosine_similarity(vec1, vec2) == 0.0

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0


# ========== Select Top-K Tests ==========


class TestSelectTopKExamples:
    def test_returns_top_k(self):
        examples = [
            {"query": "查询订单状态"},
            {"query": "查询订单详情"},
            {"query": "退款申请"},
            {"query": "换货流程"},
        ]
        result = select_top_k_examples("查询订单", examples, k=2)
        assert len(result) <= 2
        assert all("查询" in ex["query"] for ex in result)

    def test_empty_examples(self):
        result = select_top_k_examples("查询订单", [], k=3)
        assert result == []

    def test_zero_score_filtered(self):
        examples = [
            {"query": "完全不同的内容"},
            {"query": "另一个不相关的话题"},
        ]
        result = select_top_k_examples("订单查询", examples, k=3)
        assert result == []

    def test_k_larger_than_examples(self):
        examples = [{"query": "查询订单"}]
        result = select_top_k_examples("查询订单", examples, k=5)
        assert len(result) == 1


# ========== Semantic Selection Tests ==========


class TestSelectTopKExamplesSemantic:
    @pytest.mark.asyncio
    async def test_fallback_to_token_overlap_on_embedding_failure(self):
        examples = [
            {"query": "查询订单状态"},
            {"query": "查询订单详情"},
            {"query": "退款申请"},
        ]
        with patch(
            "app.retrieval.embeddings.create_embedding_model",
            side_effect=RuntimeError("embedding failed"),
        ):
            result = await select_top_k_examples_semantic("查询订单", examples, k=2)
            assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_uses_semantic_when_available(self):
        examples = [
            {"query": "查询订单状态"},
            {"query": "查询订单详情"},
            {"query": "退款申请"},
        ]
        mock_model = AsyncMock()
        mock_model.aembed_query.return_value = [1.0, 0.0, 0.0]
        mock_model.aembed_documents.return_value = [
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.0, 1.0, 0.0],
        ]

        with patch(
            "app.retrieval.embeddings.create_embedding_model",
            return_value=mock_model,
        ):
            result = await select_top_k_examples_semantic("查询订单", examples, k=2)
            assert len(result) <= 2
            mock_model.aembed_query.assert_called_once()
            mock_model.aembed_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_token_overlap_mode(self):
        examples = [
            {"query": "查询订单状态"},
            {"query": "查询订单详情"},
            {"query": "退款申请"},
        ]
        result = await select_top_k_examples_semantic("查询订单", examples, k=2, use_semantic=False)
        assert len(result) <= 2
        assert all("查询" in ex["query"] for ex in result)


# ========== Format Tests ==========


class TestFormatIntentExamplesForPrompt:
    def test_empty_examples(self):
        result = format_intent_examples_for_prompt([])
        assert result == ""

    def test_formatted_output(self):
        examples = [
            {
                "query": "查订单",
                "primary_intent": "ORDER",
                "secondary_intent": "QUERY",
                "tertiary_intent": None,
                "slots": {"order_sn": "SN123"},
                "reasoning": "用户想查订单",
            }
        ]
        result = format_intent_examples_for_prompt(examples)
        assert "查订单" in result
        assert "ORDER" in result
        assert "QUERY" in result
        assert "SN123" in result
        assert "用户想查订单" in result

    def test_with_tertiary_intent(self):
        examples = [
            {
                "query": "查订单",
                "primary_intent": "ORDER",
                "secondary_intent": "QUERY",
                "tertiary_intent": "ORDER_TRACKING",
                "slots": {},
            }
        ]
        result = format_intent_examples_for_prompt(examples)
        assert "ORDER_TRACKING" in result


class TestFormatComplaintExamplesForPrompt:
    def test_empty_examples(self):
        result = format_complaint_examples_for_prompt([])
        assert result == ""

    def test_formatted_output(self):
        examples = [
            {
                "query": "商品质量问题",
                "complaint_category": "PRODUCT_DEFECT",
                "urgency": "high",
                "expected_action": "退款",
                "reasoning": "质量问题应退款",
            }
        ]
        result = format_complaint_examples_for_prompt(examples)
        assert "商品质量问题" in result
        assert "PRODUCT_DEFECT" in result
        assert "high" in result
        assert "退款" in result


class TestFormatAgentExamplesForPrompt:
    def test_empty_examples(self):
        result = format_agent_examples_for_prompt("order", [])
        assert result == ""

    def test_order_examples(self):
        examples = [
            {
                "query": "查订单状态",
                "expected_intent": "ORDER",
                "expected_action": "QUERY",
                "slots": {"order_sn": "SN123"},
                "reasoning": "用户查询订单",
            }
        ]
        result = format_agent_examples_for_prompt("order", examples)
        assert "查订单状态" in result
        assert "ORDER" in result
        assert "QUERY" in result
        assert "SN123" in result
        assert "订单处理" in result

    def test_product_examples(self):
        examples = [
            {
                "query": "这个商品有货吗",
                "expected_intent": "PRODUCT",
                "expected_action": "QUERY",
                "reasoning": "用户询问库存",
            }
        ]
        result = format_agent_examples_for_prompt("product", examples)
        assert "商品查询" in result
        assert "这个商品有货吗" in result

    def test_unknown_agent_type(self):
        examples = [{"query": "test", "expected_intent": "TEST"}]
        result = format_agent_examples_for_prompt("unknown", examples)
        assert "test" in result
        assert "TEST" in result

    def test_complaint_category_and_urgency(self):
        examples = [
            {
                "query": "商品破损",
                "expected_intent": "COMPLAINT",
                "expected_action": "APPLY",
                "complaint_category": "PRODUCT_DEFECT",
                "urgency": "high",
                "reasoning": "商品破损",
            }
        ]
        result = format_agent_examples_for_prompt("complaint", examples)
        assert "PRODUCT_DEFECT" in result
        assert "high" in result


# ========== Integration Tests ==========


class TestFewShotIntegration:
    def test_all_agent_example_files_exist(self):
        base_dir = Path(__file__).resolve().parent.parent.parent / "data" / "prompt_examples"
        for agent_type in [
            "order",
            "product",
            "cart",
            "payment",
            "logistics",
            "account",
            "policy",
            "complaint",
            "router",
        ]:
            file_path = base_dir / agent_type / "general.jsonl"
            assert file_path.exists(), f"Missing example file: {file_path}"

    def test_all_agent_examples_valid_jsonl(self):
        base_dir = Path(__file__).resolve().parent.parent.parent / "data" / "prompt_examples"
        for agent_type in [
            "order",
            "product",
            "cart",
            "payment",
            "logistics",
            "account",
            "policy",
            "complaint",
            "router",
        ]:
            file_path = base_dir / agent_type / "general.jsonl"
            with file_path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        assert "query" in data, f"Missing 'query' in {file_path}:{line_num}"
                        has_intent = (
                            "expected_intent" in data
                            or "primary_intent" in data
                            or "complaint_category" in data
                        )
                        assert has_intent, f"Missing intent in {file_path}:{line_num}"
                    except json.JSONDecodeError as exc:
                        pytest.fail(f"Invalid JSON in {file_path}:{line_num}: {exc}")

    def test_example_count_per_agent(self):
        for agent_type in [
            "order",
            "product",
            "cart",
            "payment",
            "logistics",
            "account",
            "policy",
            "complaint",
            "router",
        ]:
            examples = load_agent_examples(agent_type)
            assert len(examples) >= 50, (
                f"Agent '{agent_type}' has only {len(examples)} examples, expected at least 50"
            )
