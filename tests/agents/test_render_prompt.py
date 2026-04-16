from unittest.mock import MagicMock

from app.agents.base import BaseAgent, render_prompt


class DummyAgent(BaseAgent):
    async def process(self, state):
        return {"response": "ok"}


def test_render_prompt_with_string_variable():
    result = render_prompt("Hello {{company_name}}", {})
    assert result == "Hello XX电商平台"


def test_render_prompt_with_callable_variable():
    result = render_prompt("Today is {{current_date}}", {})
    assert "{{current_date}}" not in result


def test_render_prompt_with_non_callable_non_string_value():
    result = render_prompt("Level: {{user_membership_level}}", {"user_membership_level": 42})
    assert result == "Level: 42"


def test_render_prompt_preserves_unknown_placeholders():
    result = render_prompt("Hello {{unknown_var}}", {})
    assert result == "Hello {{unknown_var}}"


def test_create_messages_avoids_double_rendering():
    mock_llm = MagicMock()
    agent = DummyAgent(name="test", llm=mock_llm, system_prompt="Welcome to {{company_name}}")
    agent._dynamic_system_prompt = None
    messages = agent._create_messages("Hello", user_context={"company_name": "TestCorp"})
    assert len(messages) == 2
    assert messages[0].content == "Welcome to TestCorp"


def test_create_messages_renders_override():
    mock_llm = MagicMock()
    agent = DummyAgent(name="test", llm=mock_llm, system_prompt="Welcome to {{company_name}}")
    agent._dynamic_system_prompt = None
    messages = agent._create_messages(
        "Hello",
        user_context={"company_name": "TestCorp"},
        system_prompt_override="Override for {{company_name}}",
    )
    assert len(messages) == 2
    assert messages[0].content == "Override for TestCorp"
