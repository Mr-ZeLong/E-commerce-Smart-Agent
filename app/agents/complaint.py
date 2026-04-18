import json
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.intent.few_shot_loader import (
    format_complaint_examples_for_prompt,
    load_complaint_examples,
    select_top_k_examples,
)
from app.models.state import AgentProcessResult, AgentState
from app.tools.complaint_tool import ComplaintTool

logger = logging.getLogger(__name__)


class ComplaintClassification(BaseModel):
    category: str = Field(description="投诉类别: product_defect, service, logistics, other")
    urgency: str = Field(description="紧急程度: low, medium, high")
    summary: str = Field(description="投诉摘要，用于生成工单标题/描述")
    expected_resolution: str = Field(
        description="期望解决方案: refund, exchange, apology, compensation"
    )
    empathetic_response: str = Field(description="对用户的同理心回复，包含工单号占位符 {ticket_id}")


_COMPLAINT_SYSTEM_PROMPT = """你是专业的用户投诉处理专家。

规则：
1. 认真倾听用户的不满，表达理解和同理心
2. 主动了解投诉的具体原因和期望的解决方案
3. 对于涉及订单、退款、物流的投诉，给出可行的处理建议
4. 如果问题超出权限范围，安抚用户并告知会升级给人工客服处理
5. 语气真诚、专业、耐心

输出要求：
- 请分析用户投诉并返回 JSON 格式：
{
  "category": "product_defect | service | logistics | other",
  "urgency": "low | medium | high",
  "summary": "投诉摘要",
  "expected_resolution": "refund | exchange | apology | compensation",
  "empathetic_response": "对用户的温暖回复，可包含 {ticket_id} 占位符"
}"""


class ComplaintAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel):
        super().__init__(name="complaint", llm=llm, system_prompt=_COMPLAINT_SYSTEM_PROMPT)
        self._tool: ComplaintTool = ComplaintTool()
        self._few_shot_examples = load_complaint_examples()

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
        question = state.get("question", "")
        user_id = state.get("user_id", 0)
        thread_id = state.get("thread_id", "")

        system_prompt = (
            self._dynamic_system_prompt or self.system_prompt or _COMPLAINT_SYSTEM_PROMPT
        )
        user_prompt = question
        if self._few_shot_examples:
            top_examples = select_top_k_examples(question, self._few_shot_examples, k=3)
            if top_examples:
                user_prompt = format_complaint_examples_for_prompt(top_examples) + "\n" + question

        messages = self._create_messages(
            user_prompt,
            memory_context=state.get("memory_context"),
            user_context=self._build_user_context(state.get("memory_context")),
            system_prompt_override=system_prompt,
            memory_context_config=state.get("memory_context_config"),
        )
        metadata = self._extract_tracing_metadata(state)
        raw_response = await self._call_llm(messages, tags=["user_visible"], metadata=metadata)

        classification = self._parse_classification(raw_response)

        try:
            ticket = await self._tool.create_ticket(
                user_id=user_id,
                thread_id=thread_id,
                category=classification.category,
                urgency=classification.urgency,
                description=classification.summary,
                expected_resolution=classification.expected_resolution,
            )
            ticket_id = ticket.get("ticket_id", "N/A")
            response_text = classification.empathetic_response.replace(
                "{ticket_id}", str(ticket_id)
            )
        except Exception:
            logger.exception("Failed to create complaint ticket")
            response_text = (
                "非常抱歉给您带来不好的体验，我们已经记录了您的问题，客服团队会尽快与您联系处理。"
            )

        return {
            "response": response_text,
            "updated_state": {"answer": response_text},
        }

    def _parse_classification(self, raw: str) -> ComplaintClassification:
        try:
            json_str = raw
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()
            data = json.loads(json_str)
            return ComplaintClassification(**data)
        except Exception:
            logger.warning("Failed to parse complaint classification JSON, using defaults")
            return ComplaintClassification(
                category="other",
                urgency="medium",
                summary=raw,
                expected_resolution="apology",
                empathetic_response=raw,
            )
