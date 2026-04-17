"""Tests for token budget management."""

import pytest

from app.context.token_budget import MemoryTokenBudget, TokenBudget


@pytest.fixture
def budget():
    return MemoryTokenBudget()


class TestTokenBudget:
    def test_estimate_tokens_returns_non_negative(self, budget):
        assert budget.estimate_tokens("hello world") >= 0

    def test_estimate_tokens_empty_string(self, budget):
        assert budget.estimate_tokens("") == 0

    def test_allocate_empty_dict(self, budget):
        assert budget.allocate({}) == {}

    def test_allocate_missing_keys_graceful(self, budget):
        context = {"user_profile": {"name": "Alice"}}
        result = budget.allocate(context)
        assert result == {"user_profile": {"name": "Alice"}}

    def test_allocate_none_values_skipped(self, budget):
        context = {
            "user_profile": {"name": "Alice"},
            "preferences": None,
            "structured_facts": None,
        }
        result = budget.allocate(context)
        assert result == {"user_profile": {"name": "Alice"}}

    def test_allocate_all_keys_missing(self, budget):
        assert budget.allocate({}) == {}


class TestMemoryTokenBudgetPruning:
    def test_allocate_under_budget_returns_all_keys(self, monkeypatch, budget):
        monkeypatch.setattr(
            "app.context.token_budget.settings.MEMORY_CONTEXT_TOKEN_BUDGET",
            10000,
        )
        context = {
            "user_profile": {"name": "Alice"},
            "preferences": [{"key": "lang", "value": "zh"}],
            "structured_facts": [{"fact": "likes tea"}],
            "interaction_summaries": [{"summary": "order inquiry"}],
            "relevant_past_messages": [{"role": "user", "content": "hi"}],
        }
        result = budget.allocate(context)
        assert result == context

    def test_allocate_prunes_relevant_past_messages_first(self, monkeypatch, budget):
        monkeypatch.setattr(
            "app.context.token_budget.settings.MEMORY_CONTEXT_TOKEN_BUDGET",
            50,
        )
        context = {
            "user_profile": {"name": "Alice"},
            "relevant_past_messages": [{"role": "user", "content": "a" * 200}],
            "interaction_summaries": [{"summary": "b"}],
        }
        result = budget.allocate(context)
        assert "user_profile" in result
        assert "relevant_past_messages" not in result
        assert "interaction_summaries" in result

    def test_allocate_prunes_interaction_summaries_after_messages(self, monkeypatch, budget):
        monkeypatch.setattr(
            "app.context.token_budget.settings.MEMORY_CONTEXT_TOKEN_BUDGET",
            50,
        )
        context = {
            "user_profile": {"name": "Alice"},
            "interaction_summaries": [{"summary": "b" * 150}],
            "structured_facts": [{"fact": "c" * 100}],
        }
        result = budget.allocate(context)
        assert "user_profile" in result
        assert "interaction_summaries" not in result
        assert "structured_facts" in result

    def test_allocate_prunes_structured_facts_after_summaries(self, monkeypatch, budget):
        monkeypatch.setattr(
            "app.context.token_budget.settings.MEMORY_CONTEXT_TOKEN_BUDGET",
            50,
        )
        context = {
            "user_profile": {"name": "Alice"},
            "structured_facts": [{"fact": "c" * 200}],
            "preferences": [{"key": "lang", "value": "zh"}],
        }
        result = budget.allocate(context)
        assert "user_profile" in result
        assert "structured_facts" not in result
        assert "preferences" in result

    def test_allocate_prunes_preferences_after_facts(self, monkeypatch, budget):
        monkeypatch.setattr(
            "app.context.token_budget.settings.MEMORY_CONTEXT_TOKEN_BUDGET",
            50,
        )
        context = {
            "user_profile": {"name": "Alice"},
            "preferences": [{"key": "lang", "value": "zh" * 200}],
        }
        result = budget.allocate(context)
        assert "user_profile" in result
        assert "preferences" not in result

    def test_allocate_never_drops_user_profile(self, monkeypatch, budget):
        monkeypatch.setattr(
            "app.context.token_budget.settings.MEMORY_CONTEXT_TOKEN_BUDGET",
            10,
        )
        context = {
            "user_profile": {"name": "Alice", "bio": "x" * 1000},
        }
        result = budget.allocate(context)
        assert result == context

    def test_allocate_drops_list_items_from_end(self, monkeypatch, budget):
        monkeypatch.setattr(
            "app.context.token_budget.settings.MEMORY_CONTEXT_TOKEN_BUDGET",
            60,
        )
        context = {
            "relevant_past_messages": [
                {"role": "user", "content": "first"},
                {"role": "user", "content": "second"},
                {"role": "user", "content": "third"},
            ],
        }
        result = budget.allocate(context)
        msgs = result.get("relevant_past_messages", [])
        if len(msgs) == 3:
            # Should still be under budget with all three
            assert msgs[-1]["content"] == "third"
        else:
            # The last item should have been dropped first
            assert not any(m["content"] == "third" for m in msgs)

    def test_allocate_empties_lower_priority_before_touching_higher(self, monkeypatch, budget):
        monkeypatch.setattr(
            "app.context.token_budget.settings.MEMORY_CONTEXT_TOKEN_BUDGET",
            50,
        )
        context = {
            "preferences": [{"key": "a", "value": "1" * 100}],
            "structured_facts": [
                {"fact": "x" * 100},
                {"fact": "y" * 100},
            ],
        }
        result = budget.allocate(context)
        # structured_facts is lower priority than preferences,
        # so it should be completely removed before preferences is touched
        assert "structured_facts" not in result
        assert "preferences" in result


class TestTokenBudgetABC:
    def test_token_budget_is_abstract(self):
        with pytest.raises(TypeError):
            TokenBudget()
