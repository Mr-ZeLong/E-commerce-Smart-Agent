"""Tests for context compaction utilities."""

import pytest

from app.memory.compactor import ContextCompactor


@pytest.fixture
def compactor():
    return ContextCompactor()


def test_compact_empty_history(compactor):
    assert compactor.compact([]) == []


def test_compact_single_user_message(compactor):
    history = [{"role": "user", "content": "hello"}]
    result = compactor.compact(history)
    assert len(result) == 1
    assert result[0]["role"] == "system"
    assert "compacted" in result[0]
    assert result[0]["original_turn_count"] == 1


def test_compact_preserves_first_user_and_last_assistant(compactor):
    history = [
        {"role": "user", "content": "What is the price?"},
        {"role": "assistant", "content": "It costs $99."},
        {"role": "user", "content": "Any discount?"},
        {"role": "assistant", "content": "Yes, 10% off."},
    ]
    result = compactor.compact(history)
    assert len(result) == 1
    summary = result[0]["content"]
    assert "What is the price?" in summary
    assert "Yes, 10% off." in summary


def test_compact_reduces_token_estimate(compactor):
    history = [
        {"role": "user", "content": "x" * 1000},
        {"role": "assistant", "content": "y" * 1000},
    ]
    result = compactor.compact(history)
    import json

    original_tokens = len(json.dumps(history, ensure_ascii=False)) // 4
    compacted_tokens = len(json.dumps(result, ensure_ascii=False)) // 4
    assert compacted_tokens < original_tokens
