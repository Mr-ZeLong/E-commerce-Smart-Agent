from app.agents.base import AgentResult


class TransferDecider:
    """根据 Specialist Agent 的结果或置信度评估结果，决定是否转人工"""

    @staticmethod
    def decide_transfer(specialist_result: AgentResult, evaluation: dict | None) -> dict:
        """
        整合最终状态，合并 specialist_result.updated_state 到最终返回字典。
        处理 Specialist 已标记 needs_human 的场景，以及系统错误回退场景。
        """
        if specialist_result.needs_human:
            final_state = {
                "answer": specialist_result.response,
                "confidence_score": specialist_result.confidence or 0.0,
                "confidence_signals": {},
                "needs_human_transfer": True,
                "transfer_reason": specialist_result.transfer_reason or "specialist_requested_transfer",
                "audit_level": "manual",
            }
        elif evaluation is not None:
            final_state = {
                "answer": specialist_result.response,
                **evaluation,
            }
        else:
            # 没有 evaluation 信息的回退场景
            final_state = {
                "answer": specialist_result.response,
                "confidence_score": 0.0,
                "confidence_signals": {},
                "needs_human_transfer": True,
                "transfer_reason": "missing_evaluation",
                "audit_level": "manual",
            }

        # 合并 Specialist 返回的状态更新（但不覆盖关键字段和内部字段）
        if specialist_result.updated_state:
            for key, value in specialist_result.updated_state.items():
                if key not in final_state and not key.startswith("_"):
                    final_state[key] = value

        return final_state
