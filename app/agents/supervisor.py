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

        执行流程：
        1. RouterAgent: 识别意图 → 决定调用哪个 Agent
        2. Specialist Agent: 执行业务逻辑
        3. ConfidenceEvaluator: 评估结果置信度
        4. 决定是否转人工或返回结果
        """
        question = state.get("question", "")
        user_id = state.get("user_id")

        print(f"[Supervisor] 开始协调: user={user_id}, question={question[:50]}...")

        # Step 1: 路由决策
        router_result = await self.router.process(state)

        # 如果 Router 直接返回了回复（如闲聊），直接返回
        if router_result.response:
            return {
                "answer": router_result.response,
                "intent": router_result.updated_state.get("intent"),
                "confidence_score": 1.0,  # 闲聊直接回答，置信度设为1
                "needs_human_transfer": False
            }

        intent = router_result.updated_state.get("intent")
        next_agent = router_result.updated_state.get("next_agent")

        print(f"[Supervisor] 意图识别: {intent}, 路由到: {next_agent}")

        # Step 2: 调用 Specialist Agent
        specialist_result = await self._call_specialist(
            next_agent=next_agent,
            state={**state, **router_result.updated_state}
        )

        # Step 3: 置信度评估
        # 收集所有必要信息
        context = specialist_result.updated_state.get("context", []) if specialist_result.updated_state else []
        answer = specialist_result.response
        retrieval_result = specialist_result.updated_state.get("retrieval_result") if specialist_result.updated_state else None

        # 使用新的信号计算模块
        from app.confidence.signals import ConfidenceSignals
        from app.models.state import AgentState

        # 构建临时状态用于信号计算
        temp_state = {
            "question": question,
            "history": state.get("history", []),
            "retrieval_result": retrieval_result,
        }

        # 计算置信度信号
        confidence_signals = ConfidenceSignals(temp_state)  # type: ignore
        signals = await confidence_signals.calculate_all(generated_answer=answer)

        # 计算综合置信度分数
        rag_score = signals["rag"].score
        llm_score = signals["llm"].score
        emotion_score = signals["emotion"].score

        # 使用配置的权重计算综合分数
        from app.core.config import settings
        weights = settings.CONFIDENCE.default_weights
        overall_score = (
            rag_score * weights["rag"] +
            llm_score * weights["llm"] +
            emotion_score * weights["emotion"]
        )

        # 判断是否转人工
        needs_transfer = overall_score < settings.CONFIDENCE.THRESHOLD

        print(f"[Supervisor] 置信度评估: {overall_score:.3f}, 转人工: {needs_transfer}")

        # Step 4: 构建最终状态
        final_state = {
            "answer": answer,
            "intent": intent,
            "confidence_score": overall_score,
            "confidence_signals": {
                "rag": {"score": rag_score, "reason": signals["rag"].reason},
                "llm": {"score": llm_score, "reason": signals["llm"].reason},
                "emotion": {"score": emotion_score, "reason": signals["emotion"].reason},
            },
            "needs_human_transfer": needs_transfer,
            "audit_level": settings.CONFIDENCE.get_audit_level(overall_score),
        }

        # 合并 Specialist 返回的状态更新
        if specialist_result.updated_state:
            final_state.update(specialist_result.updated_state)

        return final_state

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
        else:
            # 默认或未知情况，返回友好提示
            return AgentResult(
                response="抱歉，我暂时无法处理这个问题。如需帮助，请联系人工客服。",
                updated_state={}
            )
