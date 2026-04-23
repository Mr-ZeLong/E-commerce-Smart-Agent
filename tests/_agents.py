from dataclasses import dataclass
from typing import Any

from app.agents.base import BaseAgent
from app.agents.evaluator import ConfidenceEvaluator
from app.agents.order import OrderAgent
from app.agents.policy import PolicyAgent
from app.agents.router import IntentRouterAgent
from app.models.state import AgentProcessResult, AgentState
from app.retrieval.retriever import HybridRetriever
from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry


class DeterministicToolRegistry(ToolRegistry):
    def __init__(self, responses=None):
        super().__init__()
        self.responses = responses or {}

    async def execute(self, name: str, state: AgentState, **kwargs) -> ToolResult:
        resp = self.responses.get(name, {})
        return ToolResult(
            output=resp.get("output", {"status": "success"}),
            source=resp.get("source", name),
        )


class DeterministicRetriever(HybridRetriever):
    def __init__(self, results=None):
        self._results = results or []

    async def retrieve(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        memory_context: dict | None = None,
        variant_top_k: int | None = None,
        variant_reranker_enabled: bool | None = None,
    ) -> list:
        return self._results


class DeterministicAgent(BaseAgent):
    def __init__(self, name="mock", process_result: dict[str, Any] | None = None):
        from tests._llm import DeterministicChatModel

        super().__init__(name=name, llm=DeterministicChatModel())
        self.process_result: dict[str, Any] = process_result or {
            "response": "",
            "updated_state": {},
        }

    async def process(self, state: AgentState) -> AgentProcessResult:
        updated: dict[str, Any] = self.process_result.get("updated_state") or {}
        return {
            "response": str(self.process_result.get("response", "")),
            "updated_state": updated,
        }


class DeterministicRouterAgent(IntentRouterAgent):
    def __init__(self, process_result=None):
        self.name = "mock"
        self.process_result = process_result or {"response": "", "updated_state": {}}
        self.llm = None
        self.system_prompt = None
        self._dynamic_system_prompt = None
        self.intent_service = None
        self.structured_manager = None

    async def process(self, state):
        return self.process_result


class DeterministicPolicyAgent(PolicyAgent):
    def __init__(self, process_result=None):
        self.name = "policy_agent"
        self.process_result = process_result or {"response": "", "updated_state": {}}
        self.llm = None
        self.system_prompt = None
        self._dynamic_system_prompt = None
        self.retriever = None

    async def process(self, state):
        return self.process_result


class DeterministicOrderAgent(OrderAgent):
    def __init__(self, process_result=None):
        self.name = "order_agent"
        self.process_result = process_result or {"response": "", "updated_state": {}}
        self.llm = None
        self.system_prompt = None
        self._dynamic_system_prompt = None
        self.order_service = None

    async def process(self, state):
        return self.process_result


class DeterministicEvaluator(ConfidenceEvaluator):
    def __init__(self, evaluate_result=None):
        from tests._llm import DeterministicChatModel

        super().__init__(llm=DeterministicChatModel())
        self.evaluate_result = evaluate_result or {
            "confidence_score": 1.0,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }

    async def evaluate(self, *args, **kwargs):
        return self.evaluate_result


class DeterministicSupervisor:
    def __init__(self, process_result=None):
        self.name = "supervisor"
        self.process_result = process_result or {
            "response": "",
            "updated_state": {
                "next_agent": "",
                "execution_mode": "serial",
                "pending_agent_results": [],
            },
        }

    async def process(self, state):
        return self.process_result


@dataclass
class FakePreference:
    preference_key: str = ""
    preference_value: str = ""


@dataclass
class FakeSummary:
    summary_text: str = ""
    resolved_intent: str = ""
    created_at: Any = None
