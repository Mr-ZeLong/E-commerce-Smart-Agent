import logging

from app.agents.base import AgentResult, BaseAgent
from app.agents.evaluator import ConfidenceEvaluator
from app.agents.orchestrator import AgentOrchestrator
from app.agents.transfer import TransferDecider

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """
    监督 Agent (Supervisor)

    职责：
    1. 协调 AgentOrchestrator、ConfidenceEvaluator、TransferDecider 完成多 Agent 工作流
    2. 作为对外统一入口，保留流程观察日志和异常处理
    """

    def __init__(self):
        super().__init__(name="supervisor", system_prompt=None)
        self.orchestrator = AgentOrchestrator()
        self.evaluator = ConfidenceEvaluator()
        self.transfer_decider = TransferDecider()

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

            logger.info(f"[Supervisor] 开始协调: user={user_id}, question={question[:50]}...")

            # Step 1: 路由决策并执行 Specialist Agent
            specialist_result = await self.orchestrator.route_and_execute(state)

            # Step 2: 如果 Router 直接返回了回复（如闲聊），直接返回
            updated_state = specialist_result.updated_state or {}
            if not updated_state.get("_router_next_agent"):
                # Router 直接返回（或 orchestrator 返回了错误）
                if updated_state.get("_error"):
                    error_reason = updated_state.get("_error_reason")
                    intent = updated_state.get("intent")
                    if error_reason == "empty_router_state":
                        return {
                            "answer": specialist_result.response,
                            "intent": intent,
                            "confidence_score": 0.0,
                            "needs_human_transfer": True,
                            "transfer_reason": "系统内部错误"
                        }
                    else:
                        return {
                            "answer": specialist_result.response,
                            "intent": intent,
                            "confidence_score": 0.0,
                            "needs_human_transfer": True,
                            "transfer_reason": "无法路由到合适的代理"
                        }

                intent = updated_state.get("intent")
                return {
                    "answer": specialist_result.response,
                    "intent": intent,
                    "confidence_score": 1.0,
                    "needs_human_transfer": False
                }

            intent = updated_state.get("_router_intent")

            logger.info(f"[Supervisor] 意图识别: {intent}, 路由到: {updated_state.get('_router_next_agent')}")

            # Step 3 & 4: 置信度评估（仅当 Specialist 未标记 needs_human 时）
            if specialist_result.needs_human:
                logger.info(f"[Supervisor] Specialist 请求人工接管: {specialist_result.transfer_reason}")
                eval_result = None
            else:
                retrieval_result = updated_state.get("retrieval_result")
                eval_result = await self.evaluator.evaluate(
                    answer=specialist_result.response,
                    question=question,
                    history=state.get("history", []),
                    retrieval_result=retrieval_result,
                )
                logger.info(f"[Supervisor] 置信度评估: {eval_result['confidence_score']:.3f}")

            # Step 5: 转人工决策并整合最终状态
            final_state = self.transfer_decider.decide_transfer(specialist_result, eval_result)
            final_state["intent"] = intent

            return final_state

        except Exception as e:
            logger.exception("[Supervisor] 协调失败")
            return {
                "answer": "抱歉，系统暂时无法处理您的请求。请稍后重试或联系人工客服。",
                "intent": "ERROR",
                "confidence_score": 0.0,
                "needs_human_transfer": True,
                "transfer_reason": f"system_error: {str(e)}",
            }
