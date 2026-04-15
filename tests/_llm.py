from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field


class _StructuredRunnable(Runnable):
    """Simple runnable that returns deterministic structured output."""

    def __init__(self, data: dict[str, Any] | BaseModel) -> None:
        self._data = data

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> dict[str, Any] | BaseModel:  # noqa: ARG002
        return self._data

    async def ainvoke(
        self, input: Any, config: Any = None, **kwargs: Any
    ) -> dict[str, Any] | BaseModel:  # noqa: ARG002
        return self._data


class _BoundToolsRunnable(Runnable):
    """Wraps DeterministicChatModel to ensure tool_calls are present."""

    def __init__(self, model: "DeterministicChatModel") -> None:
        self._model = model

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> AIMessage:  # noqa: ARG002
        result = self._model.invoke(input, config, **kwargs)
        if not hasattr(result, "tool_calls") or result.tool_calls is None:
            return AIMessage(content=getattr(result, "content", ""), tool_calls=[])
        return result

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> AIMessage:  # noqa: ARG002
        result = await self._model.ainvoke(input, config, **kwargs)
        if not hasattr(result, "tool_calls") or result.tool_calls is None:
            return AIMessage(content=getattr(result, "content", ""), tool_calls=[])
        return result


class DeterministicChatModel(BaseChatModel):
    """Deterministic chat model for testing that matches inputs against patterns.

    Supports text responses via ``responses``, structured output via
    ``structured``, and tool calling via ``tool_calls``. Patterns in
    ``responses`` are checked in order; the first match wins. If no pattern
    matches, an empty string is returned.
    """

    responses: list[tuple[str | list[str], str]] = Field(default_factory=list)
    structured: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    exception: Exception | None = Field(default=None)

    @property
    def _llm_type(self) -> str:
        return "deterministic"

    def with_structured_output(self, schema, **kwargs):  # noqa: ARG002
        """Return a runnable that yields the pre-configured structured data."""
        key = getattr(schema, "__name__", None)
        if key and isinstance(self.structured, dict) and key in self.structured:
            data = self.structured[key]
        else:
            data = self.structured

        # Only validate dicts into Pydantic models when the dict is empty or
        # when we want a default instance. Otherwise return data as-is so
        # callers can handle both valid models and invalid dicts.
        if (
            data is None
            and schema is not None
            and isinstance(schema, type)
            and issubclass(schema, BaseModel)
        ):
            data = schema.model_construct()

        return _StructuredRunnable(data)

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return _BoundToolsRunnable(self)

    def _match(self, content: str) -> str:
        for patterns, response in self.responses:
            if isinstance(patterns, str):
                if patterns in content:
                    return response
            else:
                if any(p in content for p in patterns):
                    return response
        return ""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.exception is not None:
            raise self.exception

        if self.tool_calls:
            content = ""
            text = ""
            normalized_tool_calls = []
            for i, tc in enumerate(self.tool_calls):
                normalized_tc = dict(tc)
                if "id" not in normalized_tc:
                    normalized_tc["id"] = f"call_{i}"
                if "type" not in normalized_tc:
                    normalized_tc["type"] = "tool_call"
                normalized_tool_calls.append(normalized_tc)
            message = AIMessage(content=content, tool_calls=normalized_tool_calls)
        else:
            content = "".join(str(m.content) for m in messages)
            text = self._match(content)
            message = AIMessage(content=text)

        generation = ChatGeneration(message=message, text=text)
        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)
