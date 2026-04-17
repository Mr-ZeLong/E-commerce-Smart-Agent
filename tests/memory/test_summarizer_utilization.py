"""Tests for utilization-based summarization trigger."""

import pytest

from app.memory.summarizer import SessionSummarizer
from app.models.state import make_agent_state


@pytest.fixture
def summarizer():
    return SessionSummarizer()


def test_should_summarize_returns_true_when_utilization_high(summarizer):
    state = make_agent_state(question="hi", history=[{"role": "user", "content": "hello"}])
    assert summarizer.should_summarize(state, utilization=0.9) is True


def test_should_summarize_returns_true_when_history_long(summarizer):
    history = [{"role": "user", "content": str(i)} for i in range(25)]
    state = make_agent_state(question="hi", history=history)
    assert summarizer.should_summarize(state, utilization=0.1) is True


def test_should_summarize_returns_false_for_short_history_low_utilization(summarizer):
    state = make_agent_state(question="hi", history=[{"role": "user", "content": "hello"}])
    assert summarizer.should_summarize(state, utilization=0.1) is False


def test_should_summarize_uses_custom_threshold(summarizer):
    state = make_agent_state(question="hi", history=[{"role": "user", "content": "hello"}])
    assert summarizer.should_summarize(state, utilization=0.6, threshold=0.5) is True
    assert summarizer.should_summarize(state, utilization=0.6, threshold=0.75) is False


def test_should_summarize_threshold_zero_triggers_immediately(summarizer):
    state = make_agent_state(question="hi", history=[{"role": "user", "content": "hello"}])
    assert summarizer.should_summarize(state, utilization=0.01, threshold=0.0) is True
