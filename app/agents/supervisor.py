from app.agents.base import AgentResult, BaseAgent
from app.agents.order import OrderAgent
from app.agents.policy import PolicyAgent
from app.agents.router import RouterAgent


class SupervisorAgent(BaseAgent):
    """
    监督 Agent (Supervisor)

    职责：
    1. 协调多个 Specialist Agent 的执行
    2. 在关键节点进行置信度评估
    3. 决定是否需要人工接管
    4. 整合最终结果返回给用户
    """

    def __init__(self):
        super().__init__(name="supervisor", system_prompt=None)

        # 初始化所有 Specialist Agents
        self.router = RouterAgent()
        self.policy_agent = PolicyAgent()
        self.order_agent = OrderAgent()

    async def process(self, state: dict) -> AgentResult:
        """
        Supervisor 入口（符合 BaseAgent 接口）
        实际调用 coordinate 方法
        """
        result = await self.coordinate(state)
        return AgentResult(
            response=result.get("answer", ""),
            updated_state=result
        )

    async def coordinate(self, state: dict) -> dict:
        """
        协调多 Agent 工作流
        """
        try:
            question = state.get("question", "")
            user_id = state.get("user_id")

            print(f"[Supervisor] 开始协调: user={user_id}, question={question[:50]}...")

            # Step 1: 路由决策
            router_result = await self.router.process(state)

            # 如果 Router 直接返回了回复（如闲聊），直接返回
            if router_result.response:
                return {
                    "answer": router_result.response,
                    "intent": router_result.updated_state.get("intent") if router_result.updated_state else None,
                    "confidence_score": 1.0,
                    "needs_human_transfer": False
                }

            if not router_result.updated_state:
                return {
                    "answer": "系统内部错误，请稍后重试。",
                    "intent": None,
                    "confidence_score": 0.0,
                    "needs_human_transfer": True,
                    "transfer_reason": "系统内部错误"
                }

            intent = router_result.updated_state.get("intent")
            next_agent = router_result.updated_state.get("next_agent")

            if not next_agent:
                return {
                    "answer": "无法确定处理该请求的专业代理，请尝试换一种方式描述您的问题。",
                    "intent": intent,
                    "confidence_score": 0.0,
                    "needs_human_transfer": True,
                    "transfer_reason": "无法路由到合适的代理"
                }

            print(f"[Supervisor] 意图识别: {intent}, 路由到: {next_agent}")

            # Step 2: 调用 Specialist Agent
            updated_state = router_result.updated_state or {}
            specialist_result = await self._call_specialist(
                next_agent=next_agent,
                state={**state, **updated_state}
            )

            # Step 3: 置信度评估
            answer = specialist_result.response
            retrieval_result = specialist_result.updated_state.get("retrieval_result") if specialist_result.updated_state else None

            # 使用新的信号计算模块
            from app.confidence.signals import ConfidenceSignals

            # 构建临时状态用于信号计算
            temp_state = {
                "question": question,
                "history": state.get("history", []),
                "retrieval_result": retrieval_result,
            }

            # 计算置信度信号
            confidence_signals = ConfidenceSignals(temp_state)  # type: ignore
            signals = await confidence_signals.calculate_all(answer)

            # 计算加权总分
            from app.core.config import settings
            weights = settings.CONFIDENCE.default_weights
            overall_score = (
                signals["rag"].score * weights["rag"] +
                signals["llm"].score * weights["llm"] +
                signals["emotion"].score * weights["emotion"]
            )

            print(f"[Supervisor] 置信度评估: {overall_score:.3f}")

            # 确定审核级别
            audit_level = settings.CONFIDENCE.get_audit_level(overall_score)
            needs_transfer = audit_level == "manual"

            # Step 4: 构建最终状态
            final_state = {
                "answer": answer,
                "intent": intent,
                "confidence_score": overall_score,
                "confidence_signals": {
                    "rag": {"score": signals["rag"].score, "reason": signals["rag"].reason},
                    "llm": {"score": signals["llm"].score, "reason": signals["llm"].reason},
                    "emotion": {"score": signals["emotion"].score, "reason": signals["emotion"].reason},
                },
                "needs_human_transfer": needs_transfer,
                "transfer_reason": "置信度不足" if needs_transfer else None,
                "audit_level": audit_level,
            }

            # 合并 Specialist 返回的状态更新（但不覆盖关键字段）
            if specialist_result.updated_state:
                for key, value in specialist_result.updated_state.items():
                    if key not in final_state:
                        final_state[key] = value

            return final_state

        except Exception as e:
            print(f"[Supervisor] 协调失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "answer": "抱歉，系统暂时无法处理您的请求。请稍后重试或联系人工客服。",
                "intent": "ERROR",
                "confidence_score": 0.0,
                "needs_human_transfer": True,
                "transfer_reason": f"system_error: {str(e)}",
            }

    async def _call_specialist(
        self,
        next_agent: str,
        state: dict
    ) -> AgentResult:
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
