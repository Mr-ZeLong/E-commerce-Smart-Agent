from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    async def execute(self, name: str, state: AgentState, **kwargs) -> ToolResult:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found")
        return await self._tools[name].execute(state, **kwargs)

    def list_tools(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]


_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return _tool_registry
