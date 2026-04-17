"""Tests for KV-Cache optimization in IntentClassifier."""

import pytest

from app.intent.classifier import IntentClassifier
from tests._llm import DeterministicChatModel


@pytest.fixture
def classifier():
    return IntentClassifier(llm=DeterministicChatModel())


def test_create_messages_puts_few_shot_in_human_message(classifier):
    classifier._few_shot_examples = [
        {"query": "check my order", "primary_intent": "ORDER", "secondary_intent": "QUERY"},
        {
            "query": "return shipping fee",
            "primary_intent": "AFTER_SALES",
            "secondary_intent": "CONSULT",
        },
    ]
    messages = classifier._create_messages("where is my order")

    assert len(messages) == 2
    assert messages[0].type == "system"
    assert messages[1].type == "human"
    assert "check my order" in messages[1].content
    assert "where is my order" in messages[1].content
