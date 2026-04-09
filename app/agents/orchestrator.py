import logging

from app.agents.base import AgentResult
from app.agents.order import OrderAgent
from app.agents.policy import PolicyAgent
from app.agents.router import IntentRouterAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """负责 Specialist Agent 的路由调度与执行"""

    def __init__(self):
        self.router = IntentRouterAgent()
        self.policy_agent = PolicyAgent()
        self.order_agent = OrderAgent()

    async def route_and_execute(self, state: dict) -> AgentResult:
        """路由决策并调用对应的 Specialist Agent"""
        router_result = await self.router.process(state)

        # Router 直接返回了回复（如闲聊、问候、需要澄清）
        if router_result.response:
            return AgentResult(
                response=router_result.response,
                updated_state=router_result.updated_state or {}
            )

        if not router_result.updated_state:
            return AgentResult(
                response="系统内部错误，请稍后重试。",
                updated_state={
                    "_error": True,
                    "_error_reason": "empty_router_state"
                }
            )

        intent = router_result.updated_state.get("intent")
        next_agent = router_result.updated_state.get("next_agent")

        if not next_agent:
            return AgentResult(
                response="无法确定处理该请求的专业代理，请尝试换一种方式描述您的问题。",
                updated_state={
                    **(router_result.updated_state or {}),
                    "_error": True,
                    "_error_reason": "no_next_agent"
                }
            )

        updated_state = router_result.updated_state or {}
        specialist_result = await self._call_specialist(
            next_agent=next_agent,
            state={**state, **updated_state}
        )

        # 在 specialist 结果中保留路由元信息，供 Supervisor 使用
        if specialist_result.updated_state is None:
            specialist_result.updated_state = {}
        specialist_result.updated_state["_router_intent"] = intent
        specialist_result.updated_state["_router_next_agent"] = next_agent

        return specialist_result

    async def _call_specialist(self, next_agent: str, state: dict) -> AgentResult:
        """调用对应的 Specialist Agent"""
        if next_agent == "policy":
            return await self.policy_agent.process(state)
        elif next_agent == "order":
            return await self.order_agent.process(state)
        elif next_agent == "supervisor":
            # 默认回退到 policy agent 处理一般性咨询
            return await self.policy_agent.process(state)
        else:
            # 默认或未知情况，返回友好提示
            return AgentResult(
                response="抱歉，我暂时无法处理这个问题。如需帮助，请联系人工客服。",
                updated_state={}
            )
