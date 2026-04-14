import pytest

from app.models.state import make_agent_state
from app.tools.base import BaseTool, ToolResult
from app.tools.registry import ToolRegistry


class MockTool(BaseTool):
    name = "mock_tool"
    description = "A mock tool for testing"

    async def execute(self, state, **kwargs):
        _ = state
        return ToolResult(output={"received": kwargs})


class AnotherMockTool(BaseTool):
    name = "another_mock"
    description = "Another mock tool"

    async def execute(self, state, **kwargs):
        _ = state
        _ = kwargs
        return ToolResult(output={"tool": "another"})


@pytest.fixture
def registry():
    return ToolRegistry()


def test_register_and_list_tools(registry):
    tool1 = MockTool()
    tool2 = AnotherMockTool()

    registry.register(tool1)
    registry.register(tool2)

    tools = registry.list_tools()
    assert len(tools) == 2
    assert {"name": "mock_tool", "description": "A mock tool for testing"} in tools
    assert {"name": "another_mock", "description": "Another mock tool"} in tools


@pytest.mark.asyncio
async def test_execute_registered_tool(registry):
    tool = MockTool()
    registry.register(tool)

    state = make_agent_state(question="test")
    result = await registry.execute("mock_tool", state, foo="bar")

    assert isinstance(result, ToolResult)
    assert result.output == {"received": {"foo": "bar"}}
    assert result.confidence == 1.0
    assert result.source == "tool"


@pytest.mark.asyncio
async def test_execute_missing_tool_raises(registry):
    state = make_agent_state(question="test")

    with pytest.raises(KeyError, match="Tool 'missing_tool' not found"):
        await registry.execute("missing_tool", state)
