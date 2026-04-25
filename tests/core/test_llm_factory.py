from unittest.mock import patch

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import maybe_add_cache_control


class TestMaybeAddCacheControl:
    def test_non_anthropic_endpoint_returns_messages_unchanged(self):
        messages = [SystemMessage(content="sys"), HumanMessage(content="user")]
        with patch("app.core.llm_factory.is_anthropic_endpoint", return_value=False):
            result = maybe_add_cache_control(messages)
        assert len(result) == 2
        assert result[0].content == "sys"
        assert result[1].content == "user"

    def test_anthropic_endpoint_marks_first_system_and_last_human(self):
        messages = [
            SystemMessage(content="sys1"),
            HumanMessage(content="user1"),
            SystemMessage(content="sys2"),
            HumanMessage(content="user2"),
        ]
        with patch("app.core.llm_factory.is_anthropic_endpoint", return_value=True):
            result = maybe_add_cache_control(messages)

        # First system message gets persistent cache
        assert isinstance(result[0].content, list)
        assert result[0].content[0]["type"] == "text"
        assert result[0].content[0]["text"] == "sys1"
        assert result[0].content[0]["cache_control"]["type"] == "persistent"

        # Intermediate messages unchanged
        assert isinstance(result[1].content, str)
        assert result[1].content == "user1"
        assert isinstance(result[2].content, str)
        assert result[2].content == "sys2"

        # Last human message gets ephemeral cache
        assert isinstance(result[3].content, list)
        assert result[3].content[0]["type"] == "text"
        assert result[3].content[0]["text"] == "user2"
        assert result[3].content[0]["cache_control"]["type"] == "ephemeral"

    def test_anthropic_with_only_system_message(self):
        messages = [SystemMessage(content="sys")]
        with patch("app.core.llm_factory.is_anthropic_endpoint", return_value=True):
            result = maybe_add_cache_control(messages)

        assert isinstance(result[0].content, list)
        assert result[0].content[0]["cache_control"]["type"] == "persistent"

    def test_anthropic_with_only_human_message(self):
        messages = [HumanMessage(content="user")]
        with patch("app.core.llm_factory.is_anthropic_endpoint", return_value=True):
            result = maybe_add_cache_control(messages)

        assert isinstance(result[0].content, list)
        assert result[0].content[0]["cache_control"]["type"] == "ephemeral"
