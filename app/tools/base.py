from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.models.state import AgentState


class ToolResult(BaseModel):
    output: dict[str, Any]
    confidence: float = 1.0
    source: str = "tool"


class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, state: AgentState, **kwargs) -> ToolResult: ...
