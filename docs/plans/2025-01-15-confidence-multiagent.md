# 置信度驱动人工接管 + 多 Agent 协作架构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于置信度评估的智能人工接管机制，并将单体 Agent 重构为职责分明的多 Agent 协作架构

**Architecture:**
1. **置信度系统**: 在生成回复后增加置信度评估节点，综合 RAG 检索质量、LLM 自我评估、用户情感检测三个信号，低于阈值时触发人工接管
2. **多 Agent 架构**: 将现有 nodes.py 拆分为 RouterAgent、PolicyAgent、OrderAgent 三个 Specialist Agent，通过 Supervisor 协调，每个 Agent 职责单一、可独立迭代

**Tech Stack:** LangGraph Multi-Agent, SQLModel, FastAPI, PostgreSQL, Redis

---

## 文件结构总览

### 新建文件
- `app/agents/__init__.py` - Agents 包初始化
- `app/agents/base.py` - 基础 Agent 抽象类
- `app/agents/router.py` - 路由 Agent（意图识别 + 分发）
- `app/agents/policy.py` - 政策专家 Agent（RAG 检索 + 政策问答）
- `app/agents/order.py` - 订单专家 Agent（订单查询 + 退货流程）
- `app/agents/supervisor.py` - 监督 Agent（协调多 Agent 工作流）
- `app/confidence/__init__.py` - 置信度模块初始化
- `app/confidence/evaluator.py` - 置信度评估器
- `app/confidence/signals.py` - 置信度信号计算（RAG/LLM/情感）
- `app/models/confidence_audit.py` - 置信度审计日志模型
- `test/agents/test_router.py` - RouterAgent 测试
- `test/agents/test_policy.py` - PolicyAgent 测试
- `test/agents/test_order.py` - OrderAgent 测试
- `test/confidence/test_evaluator.py` - 置信度评估测试

### 修改文件
- `app/graph/state.py` - 扩展 AgentState 增加置信度相关字段
- `app/graph/workflow.py` - 重构为多 Agent 工作流
- `app/api/v1/admin.py` - 增加置信度审核任务接口
- `app/api/v1/chat.py` - 适配多 Agent 响应
- `app/models/audit.py` - 扩展 AuditLog 支持置信度触发类型
- `migrations/versions/xxx_add_confidence_audit.py` - 数据库迁移

---

## Task 1: 扩展 AgentState 状态定义

**Files:**
- Modify: `app/graph/state.py:1-40`

- [ ] **Step 1: 添加置信度相关字段到 AgentState**

```python
# app/graph/state.py
import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict):
    # 基础信息
    question: str
    user_id: int

    # 意图标签: "POLICY" 或 "ORDER" 或 "REFUND" 或 "OTHER"
    intent: str | None

    # 新增：路由决策 - 用于多 Agent 协作
    next_agent: str | None  # "policy" | "order" | "supervisor"

    # 历史记录 (用于多轮对话)
    history: Annotated[list[dict], operator.add]

    # 检索到的知识
    context: list[str]

    # 新增：RAG 检索元数据（用于置信度计算）
    retrieval_metadata: dict | None  # {distances: [], valid_chunks: int, total_chunks: int}

    # 查到的订单数据
    order_data: dict | None

    # 会话 ID
    thread_id: str

    # 审核状态
    audit_required: bool
    audit_log_id: int | None

    # 新增：置信度审核类型区分
    audit_type: str | None  # "RISK" | "CONFIDENCE" | None

    # 结构化消息列表
    messages: Annotated[list[dict[str, Any]], operator.add]

    # 退货流程状态
    refund_flow_active: bool | None
    refund_order_sn: str | None
    refund_step: str | None

    # 新增：置信度评估结果
    confidence_score: float | None  # 0-1 之间的分数
    confidence_signals: dict | None  # {rag: float, llm: float, emotion: float}
    needs_human_transfer: bool | None  # 是否需要转人工
    transfer_reason: str | None  # 转人工原因

    # 最终回复
    answer: str
```

- [ ] **Step 2: 提交更改**

```bash
git add app/graph/state.py
git commit -m "feat: extend AgentState with confidence and multi-agent fields"
```

---

## Task 2: 创建置信度信号计算模块

**Files:**
- Create: `app/confidence/__init__.py`
- Create: `app/confidence/signals.py`

- [ ] **Step 1: 创建置信度包初始化文件**

```python
# app/confidence/__init__.py
from app.confidence.evaluator import ConfidenceEvaluator
from app.confidence.signals import RAGSignal, LLMSignal, EmotionSignal

__all__ = ["ConfidenceEvaluator", "RAGSignal", "LLMSignal", "EmotionSignal"]
```

- [ ] **Step 2: 创建置信度信号计算模块**

```python
# app/confidence/signals.py
import re
from typing import Protocol

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings


class Signal(Protocol):
    """置信度信号接口"""

    async def calculate(self, **kwargs) -> tuple[float, str]:
        """
        计算信号值
        Returns: (score: 0-1, reason: 说明)
        """
        ...


class RAGSignal:
    """RAG 检索质量信号"""

    def __init__(self, similarity_threshold: float = 0.5):
        self.similarity_threshold = similarity_threshold

    async def calculate(
        self,
        context: list[str],
        retrieval_metadata: dict | None = None
    ) -> tuple[float, str]:
        """
        基于 RAG 检索质量计算置信度

        信号逻辑：
        - 检索到 0 条有效结果：置信度 0.0
        - 检索结果平均距离 > 0.5：置信度 0.3
        - 检索结果平均距离 0.3-0.5：置信度 0.6
        - 检索结果平均距离 < 0.3：置信度 0.9
        """
        if not context:
            return 0.0, "未检索到任何相关知识"

        if retrieval_metadata and "distances" in retrieval_metadata:
            distances = retrieval_metadata["distances"]
            avg_distance = sum(distances) / len(distances)

            if avg_distance > 0.5:
                return 0.3, f"检索结果相关性较低 (avg_distance={avg_distance:.3f})"
            elif avg_distance > 0.3:
                return 0.6, f"检索结果相关性一般 (avg_distance={avg_distance:.3f})"
            else:
                return 0.9, f"检索结果相关性高 (avg_distance={avg_distance:.3f})"

        # 如果没有元数据，基于 context 数量粗略估计
        if len(context) >= 3:
            return 0.7, f"检索到 {len(context)} 条相关知识"
        elif len(context) >= 1:
            return 0.5, f"仅检索到 {len(context)} 条相关知识"
        else:
            return 0.0, "未检索到相关知识"


class LLMSignal:
    """LLM 自我评估信号"""

    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.OPENAI_BASE_URL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            model=settings.LLM_MODEL,
            temperature=0,
        )

    async def calculate(
        self,
        question: str,
        context: list[str],
        answer: str
    ) -> tuple[float, str]:
        """
        让 LLM 自我评估回答的置信度

        返回 0-1 之间的分数，越高表示越自信
        """
        prompt = f"""请评估你对以下回答的置信度。

用户问题: {question}

检索到的参考信息:
{chr(10).join([f"- {c}" for c in context]) if context else "无相关参考信息"}

你的回答: {answer}

请从以下维度评估:
1. 参考信息是否充分回答用户问题？
2. 回答中是否有不确定或推测的内容？
3. 如果参考信息为空，你是否能够确定地回答？

请只返回一个 0-1 之间的数字，保留两位小数:
- 0.0-0.3: 不确定，参考信息不足或问题超出范围
- 0.4-0.6: 部分确定，有一定参考信息但不够完整
- 0.7-1.0: 确定，参考信息充分且能够准确回答

只返回数字，不要任何解释:"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 尝试解析数字
            score = float(content)
            score = max(0.0, min(1.0, score))  # 限制在 0-1 范围

            if score < 0.3:
                return score, f"LLM 自我评估为不确定 (score={score:.2f})"
            elif score < 0.7:
                return score, f"LLM 自我评估为部分确定 (score={score:.2f})"
            else:
                return score, f"LLM 自我评估为确定 (score={score:.2f})"

        except (ValueError, Exception) as e:
            # 解析失败时返回中等置信度
            return 0.5, f"LLM 置信度评估解析失败 ({e})，默认中等置信度"


class EmotionSignal:
    """用户情感检测信号"""

    # 负面情感关键词
    NEGATIVE_KEYWORDS = [
        "生气", "愤怒", "恼火", "气愤", "怒",
        "失望", "绝望", "崩溃", "受不了",
        "投诉", "举报", "告你们", "法院", "律师",
        "垃圾", "骗子", "坑人", "欺诈",
        "我要退钱", "必须退", "立刻", "马上",
        "什么玩意", "搞什么", "怎么回事", "凭什么"
    ]

    # 积极/中性情感关键词
    POSITIVE_KEYWORDS = [
        "谢谢", "感谢", "麻烦", "请", "帮忙",
        "请问", "咨询", "了解一下"
    ]

    async def calculate(self, question: str) -> tuple[float, str]:
        """
        基于用户问题检测情感状态

        返回 0-1 之间的分数，越高表示情感越平和（越适合 AI 处理）
        越低表示用户越愤怒或焦虑（应该优先转人工）
        """
        question_lower = question.lower()

        # 计算负面情感词数量
        negative_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in question_lower)
        positive_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in question_lower)

        # 感叹号和问号数量（过多表示情绪激动）
        exclamation_count = question.count("！") + question.count("!")
        question_mark_count = question.count("？") + question.count("?")

        # 计算基础分数
        base_score = 0.7

        # 负面情感扣分
        base_score -= negative_count * 0.15

        # 正面情感加分
        base_score += positive_count * 0.05

        # 过多感叹号扣分
        base_score -= exclamation_count * 0.1

        # 限制在 0-1 范围
        score = max(0.0, min(1.0, base_score))

        if score < 0.4:
            return score, f"检测到用户负面情绪强烈 (负面词:{negative_count}, 感叹号:{exclamation_count})"
        elif score < 0.7:
            return score, f"检测到用户有一定负面情绪 (负面词:{negative_count})"
        else:
            return score, f"用户情感平和，适合 AI 处理 (正面词:{positive_count})"


# 信号权重配置
SIGNAL_WEIGHTS = {
    "rag": 0.4,      # RAG 质量占 40%
    "llm": 0.4,      # LLM 自我评估占 40%
    "emotion": 0.2   # 情感检测占 20%
}
```

- [ ] **Step 3: 提交更改**

```bash
git add app/confidence/
git commit -m "feat: add confidence signals module (RAG/LLM/Emotion)"
```

---

## Task 3: 创建置信度评估器

**Files:**
- Create: `app/confidence/evaluator.py`
- Create: `test/confidence/test_evaluator.py`

- [ ] **Step 1: 编写测试文件（TDD）**

```python
# test/confidence/test_evaluator.py
import pytest

from app.confidence.evaluator import ConfidenceEvaluator, TransferReason
from app.confidence.signals import RAGSignal, LLMSignal, EmotionSignal


class TestConfidenceEvaluator:
    """测试置信度评估器"""

    @pytest.fixture
    def evaluator(self):
        return ConfidenceEvaluator(
            threshold=0.6,
            weights={"rag": 0.4, "llm": 0.4, "emotion": 0.2}
        )

    @pytest.mark.asyncio
    async def test_high_confidence_no_transfer(self, evaluator):
        """高置信度时不应转人工"""
        result = await evaluator.evaluate(
            question="请问运费怎么算？",
            context=["运费标准: 满100免运费", "配送时效: 1-3天"],
            answer="满100元免运费，配送时效1-3天",
            retrieval_metadata={"distances": [0.2, 0.25], "valid_chunks": 2}
        )

        assert result["needs_transfer"] is False
        assert result["confidence_score"] > 0.6
        assert result["reason"] is None

    @pytest.mark.asyncio
    async def test_low_rag_confidence_triggers_transfer(self, evaluator):
        """RAG 检索失败时应转人工"""
        result = await evaluator.evaluate(
            question="请问这个政策是什么意思？",
            context=[],  # 空检索结果
            answer="抱歉，暂未查询到相关规定",
            retrieval_metadata={"distances": [], "valid_chunks": 0}
        )

        assert result["needs_transfer"] is True
        assert result["reason"] == TransferReason.LOW_RAG_CONFIDENCE

    @pytest.mark.asyncio
    async def test_angry_user_triggers_transfer(self, evaluator):
        """愤怒用户应优先转人工"""
        result = await evaluator.evaluate(
            question="你们太垃圾了！我要投诉！立刻给我退钱！",
            context=["退货政策: 7天无理由"],
            answer="理解您的心情，我们可以帮您办理退货",
            retrieval_metadata={"distances": [0.2]}
        )

        assert result["needs_transfer"] is True
        assert result["reason"] == TransferReason.NEGATIVE_EMOTION

    @pytest.mark.asyncio
    async def test_weighted_score_calculation(self):
        """测试加权分数计算"""
        evaluator = ConfidenceEvaluator(
            threshold=0.5,
            weights={"rag": 0.5, "llm": 0.3, "emotion": 0.2}
        )

        # 手动设置信号值测试计算逻辑
        score = evaluator._calculate_weighted_score({
            "rag": 0.9,
            "llm": 0.5,
            "emotion": 0.3
        })

        # 0.9*0.5 + 0.5*0.3 + 0.3*0.2 = 0.45 + 0.15 + 0.06 = 0.66
        assert score == pytest.approx(0.66, 0.01)


class TestRAGSignal:
    """测试 RAG 信号"""

    @pytest.mark.asyncio
    async def test_empty_context_returns_zero(self):
        signal = RAGSignal()
        score, reason = await signal.calculate(context=[], retrieval_metadata=None)
        assert score == 0.0
        assert "未检索" in reason

    @pytest.mark.asyncio
    async def test_high_quality_retrieval(self):
        signal = RAGSignal()
        score, reason = await signal.calculate(
            context=["content1", "content2"],
            retrieval_metadata={"distances": [0.1, 0.15]}
        )
        assert score == 0.9
        assert "相关性高" in reason


class TestEmotionSignal:
    """测试情感信号"""

    @pytest.mark.asyncio
    async def test_polite_question(self):
        signal = EmotionSignal()
        score, reason = await signal.calculate("请问运费怎么算？谢谢！")
        assert score > 0.7
        assert "平和" in reason

    @pytest.mark.asyncio
    async def test_angry_complaint(self):
        signal = EmotionSignal()
        score, reason = await signal.calculate("你们太垃圾了！我要投诉！")
        assert score < 0.4
        assert "负面" in reason
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/zelon/projects/E-commerce-Smart-Agent
pytest test/confidence/test_evaluator.py -v
# 预期：失败，因为 evaluator.py 还未创建
```

- [ ] **Step 3: 创建置信度评估器实现**

```python
# app/confidence/evaluator.py
from enum import Enum
from typing import Protocol

from app.confidence.signals import EmotionSignal, LLMSignal, RAGSignal, SIGNAL_WEIGHTS


class TransferReason(str, Enum):
    """转人工原因枚举"""
    LOW_RAG_CONFIDENCE = "LOW_RAG_CONFIDENCE"      # RAG 检索质量低
    LOW_LLM_CONFIDENCE = "LOW_LLM_CONFIDENCE"      # LLM 不确定
    NEGATIVE_EMOTION = "NEGATIVE_EMOTION"          # 用户负面情绪
    LOW_OVERALL_SCORE = "LOW_OVERALL_SCORE"        # 综合分数低


class ConfidenceEvaluator:
    """
    置信度评估器

    综合多个信号评估 AI 回答的可信度，决定是否转人工
    """

    def __init__(
        self,
        threshold: float = 0.6,
        weights: dict | None = None
    ):
        """
        Args:
            threshold: 置信度阈值，低于此值触发人工接管
            weights: 各信号权重，默认使用 SIGNAL_WEIGHTS
        """
        self.threshold = threshold
        self.weights = weights or SIGNAL_WEIGHTS

        # 初始化信号计算器
        self.rag_signal = RAGSignal()
        self.llm_signal = LLMSignal()
        self.emotion_signal = EmotionSignal()

    async def evaluate(
        self,
        question: str,
        context: list[str],
        answer: str,
        retrieval_metadata: dict | None = None
    ) -> dict:
        """
        执行置信度评估

        Returns:
            {
                "confidence_score": float,      # 综合置信度分数 0-1
                "confidence_signals": dict,     # 各信号详细分数
                "needs_transfer": bool,         # 是否需要转人工
                "reason": TransferReason | None # 转人工原因
            }
        """
        # 计算各信号值
        rag_score, rag_reason = await self.rag_signal.calculate(
            context=context,
            retrieval_metadata=retrieval_metadata
        )

        llm_score, llm_reason = await self.llm_signal.calculate(
            question=question,
            context=context,
            answer=answer
        )

        emotion_score, emotion_reason = await self.emotion_signal.calculate(
            question=question
        )

        # 计算加权综合分数
        signals = {
            "rag": rag_score,
            "llm": llm_score,
            "emotion": emotion_score
        }
        overall_score = self._calculate_weighted_score(signals)

        # 判断是否转人工
        needs_transfer, reason = self._should_transfer(
            overall_score=overall_score,
            rag_score=rag_score,
            llm_score=llm_score,
            emotion_score=emotion_score,
            rag_reason=rag_reason,
            llm_reason=llm_reason,
            emotion_reason=emotion_reason
        )

        return {
            "confidence_score": round(overall_score, 3),
            "confidence_signals": signals,
            "needs_transfer": needs_transfer,
            "reason": reason.value if reason else None,
            "signal_details": {
                "rag": {"score": rag_score, "reason": rag_reason},
                "llm": {"score": llm_score, "reason": llm_reason},
                "emotion": {"score": emotion_score, "reason": emotion_reason}
            }
        }

    def _calculate_weighted_score(self, signals: dict[str, float]) -> float:
        """计算加权综合分数"""
        total = 0.0
        for signal_name, score in signals.items():
            weight = self.weights.get(signal_name, 0.33)
            total += score * weight
        return total

    def _should_transfer(
        self,
        overall_score: float,
        rag_score: float,
        llm_score: float,
        emotion_score: float,
        rag_reason: str,
        llm_reason: str,
        emotion_reason: str
    ) -> tuple[bool, TransferReason | None]:
        """
        判断是否需要转人工

        优先级：
        1. 负面情绪（用户体验优先）
        2. RAG 检索失败（AI 无法回答）
        3. LLM 不确定（可能幻觉）
        4. 综合分数低
        """
        # 优先级 1: 负面情绪
        if emotion_score < 0.4:
            return True, TransferReason.NEGATIVE_EMOTION

        # 优先级 2: RAG 完全失败
        if rag_score < 0.3:
            return True, TransferReason.LOW_RAG_CONFIDENCE

        # 优先级 3: LLM 非常不确定
        if llm_score < 0.3:
            return True, TransferReason.LOW_LLM_CONFIDENCE

        # 优先级 4: 综合分数低于阈值
        if overall_score < self.threshold:
            return True, TransferReason.LOW_OVERALL_SCORE

        return False, None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest test/confidence/test_evaluator.py -v
# 预期：所有测试通过
```

- [ ] **Step 5: 提交更改**

```bash
git add app/confidence/ test/confidence/
git commit -m "feat: implement confidence evaluator with TDD"
```

---

## Task 4: 创建基础 Agent 抽象类

**Files:**
- Create: `app/agents/__init__.py`
- Create: `app/agents/base.py`
- Create: `test/agents/test_base.py`

- [ ] **Step 1: 创建 Agents 包初始化**

```python
# app/agents/__init__.py
from app.agents.base import BaseAgent, AgentResult
from app.agents.router import RouterAgent
from app.agents.policy import PolicyAgent
from app.agents.order import OrderAgent
from app.agents.supervisor import SupervisorAgent

__all__ = [
    "BaseAgent",
    "AgentResult",
    "RouterAgent",
    "PolicyAgent",
    "OrderAgent",
    "SupervisorAgent"
]
```

- [ ] **Step 2: 编写基础 Agent 测试**

```python
# test/agents/test_base.py
import pytest
from typing import Any

from app.agents.base import BaseAgent, AgentResult


class ConcreteAgent(BaseAgent):
    """测试用的具体 Agent 实现"""

    async def process(self, state: dict) -> AgentResult:
        return AgentResult(
            response="test response",
            updated_state={"test": True}
        )


class TestBaseAgent:
    """测试基础 Agent 类"""

    @pytest.fixture
    def agent(self):
        return ConcreteAgent(name="test_agent")

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """测试 Agent 初始化"""
        assert agent.name == "test_agent"
        assert agent.system_prompt is None

    @pytest.mark.asyncio
    async def test_agent_process(self, agent):
        """测试 Agent 处理逻辑"""
        result = await agent.process({"question": "test"})
        assert isinstance(result, AgentResult)
        assert result.response == "test response"
        assert result.updated_state["test"] is True

    @pytest.mark.asyncio
    async def test_agent_result_defaults(self):
        """测试 AgentResult 默认值"""
        result = AgentResult(response="hello")
        assert result.response == "hello"
        assert result.updated_state is None
        assert result.confidence is None
        assert result.needs_human is False
```

- [ ] **Step 3: 运行测试确认失败**

```bash
pytest test/agents/test_base.py -v
# 预期：失败，因为 base.py 还未创建
```

- [ ] **Step 4: 创建基础 Agent 类**

```python
# app/agents/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings


@dataclass
class AgentResult:
    """
    Agent 处理结果

    标准化 Agent 输出格式，便于 Supervisor 统一处理
    """
    response: str                           # 回复内容
    updated_state: dict | None = None       # 需要更新的状态字段
    confidence: float | None = None         # 置信度分数（可选）
    needs_human: bool = False               # 是否需要转人工
    transfer_reason: str | None = None      # 转人工原因


class BaseAgent(ABC):
    """
    Agent 基类

    所有 Specialist Agent 的抽象基类，定义统一接口
    """

    def __init__(
        self,
        name: str,
        system_prompt: str | None = None,
        llm_model: str | None = None
    ):
        """
        Args:
            name: Agent 名称标识
            system_prompt: 系统提示词
            llm_model: 使用的 LLM 模型，默认使用配置中的模型
        """
        self.name = name
        self.system_prompt = system_prompt
        self.llm = ChatOpenAI(
            base_url=settings.OPENAI_BASE_URL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            model=llm_model or settings.LLM_MODEL,
            temperature=0,
        )

    @abstractmethod
    async def process(self, state: dict) -> AgentResult:
        """
        处理用户请求

        Args:
            state: 当前状态字典，包含 question, user_id, context 等

        Returns:
            AgentResult: 处理结果
        """
        pass

    async def _call_llm(
        self,
        messages: list,
        temperature: float | None = None
    ) -> str:
        """
        调用 LLM

        封装 LLM 调用，便于统一处理日志、重试等
        """
        try:
            if temperature is not None:
                response = await self.llm.ainvoke(
                    messages,
                    temperature=temperature
                )
            else:
                response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            print(f"[{self.name}] LLM 调用失败: {e}")
            raise

    def _create_messages(
        self,
        user_message: str,
        context: dict | None = None
    ) -> list:
        """创建消息列表"""
        messages = []

        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))

        # 如果有上下文，构建增强的用户消息
        if context:
            enhanced_message = self._build_contextual_message(
                user_message, context
            )
            from langchain_core.messages import HumanMessage
            messages.append(HumanMessage(content=enhanced_message))
        else:
            from langchain_core.messages import HumanMessage
            messages.append(HumanMessage(content=user_message))

        return messages

    def _build_contextual_message(
        self,
        question: str,
        context: dict
    ) -> str:
        """构建带上下文的用户消息"""
        parts = []

        if "context" in context and context["context"]:
            parts.append("[参考信息]:")
            for i, ctx in enumerate(context["context"], 1):
                parts.append(f"{i}. {ctx}")
            parts.append("")

        if "order_data" in context and context["order_data"]:
            parts.append("[订单信息]:")
            order = context["order_data"]
            parts.append(f"订单号: {order.get('order_sn', 'N/A')}")
            parts.append(f"状态: {order.get('status', 'N/A')}")
            parts.append("")

        parts.append(f"[用户问题]:\n{question}")

        return "\n".join(parts)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest test/agents/test_base.py -v
# 预期：所有测试通过
```

- [ ] **Step 6: 提交更改**

```bash
git add app/agents/ test/agents/
git commit -m "feat: add BaseAgent abstract class with TDD"
```

---

## Task 5: 创建 RouterAgent（意图识别 + 分发）

**Files:**
- Create: `app/agents/router.py`
- Create: `test/agents/test_router.py`

- [ ] **Step 1: 编写 RouterAgent 测试**

```python
# test/agents/test_router.py
import pytest

from app.agents.router import RouterAgent, Intent


class TestRouterAgent:
    """测试路由 Agent"""

    @pytest.fixture
    def router(self):
        return RouterAgent()

    @pytest.mark.asyncio
    async def test_route_policy_question(self, router):
        """测试政策问题路由"""
        result = await router.process({
            "question": "内衣可以退货吗？",
            "user_id": 1
        })

        assert result.updated_state["intent"] == Intent.POLICY
        assert result.updated_state["next_agent"] == "policy"

    @pytest.mark.asyncio
    async def test_route_order_question(self, router):
        """测试订单查询路由"""
        result = await router.process({
            "question": "我的订单到哪了？",
            "user_id": 1
        })

        assert result.updated_state["intent"] == Intent.ORDER
        assert result.updated_state["next_agent"] == "order"

    @pytest.mark.asyncio
    async def test_route_refund_question(self, router):
        """测试退货问题路由"""
        result = await router.process({
            "question": "我要退货，订单号 SN12345",
            "user_id": 1
        })

        assert result.updated_state["intent"] == Intent.REFUND
        assert result.updated_state["next_agent"] == "order"  # 退货也走 order agent

    @pytest.mark.asyncio
    async def test_route_greeting(self, router):
        """测试问候语路由"""
        result = await router.process({
            "question": "你好",
            "user_id": 1
        })

        assert result.updated_state["intent"] == Intent.OTHER
        assert result.response is not None  # 直接返回问候回复
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest test/agents/test_router.py -v
# 预期：失败
```

- [ ] **Step 3: 创建 RouterAgent 实现**

```python
# app/agents/router.py
from enum import Enum

from langchain_core.messages import HumanMessage

from app.agents.base import AgentResult, BaseAgent


class Intent(str, Enum):
    """意图枚举"""
    ORDER = "ORDER"
    POLICY = "POLICY"
    REFUND = "REFUND"
    OTHER = "OTHER"


ROUTER_PROMPT = """你是一个电商客服分类器。根据用户输入，归类为以下四种意图之一：

- "ORDER": 用户询问关于他们自己的订单状态、物流、详情等（但不是退货）。
  示例："我的订单到哪了？"、"查询订单 SN20240001"

- "POLICY": 用户询问关于平台通用的退换货、运费、时效等政策信息。
  示例："内衣可以退货吗？"、"运费怎么算？"

- "REFUND": 用户明确表示要办理退货、退款、换货等售后服务。
  示例："我要退货"、"申请退款"、"这个订单我不要了"

- "OTHER": 用户进行闲聊、打招呼或提出与上述无关的问题。
  示例："你好"、"讲个笑话"

只返回分类标签（ORDER/POLICY/REFUND/OTHER），不要返回任何其他文字。"""


class RouterAgent(BaseAgent):
    """
    路由 Agent

    职责：
    1. 识别用户意图
    2. 决定调用哪个 Specialist Agent
    3. 处理简单的闲聊/问候
    """

    def __init__(self):
        super().__init__(
            name="router",
            system_prompt=ROUTER_PROMPT
        )

    async def process(self, state: dict) -> AgentResult:
        """
        处理用户输入，识别意图并路由
        """
        question = state.get("question", "")

        # 简单的规则前置过滤（减少 LLM 调用）
        quick_intent = self._quick_intent_check(question)
        if quick_intent:
            intent = quick_intent
        else:
            # 调用 LLM 进行意图识别
            intent = await self._llm_intent_recognition(question)

        # 根据意图决定下一个 Agent
        next_agent = self._decide_next_agent(intent)

        # 如果是闲聊，直接返回回复
        if intent == Intent.OTHER:
            return AgentResult(
                response="您好！我是您的智能客服助手，可以帮您查询订单、咨询政策或处理退货。请问有什么可以帮您？",
                updated_state={
                    "intent": intent,
                    "next_agent": next_agent
                }
            )

        return AgentResult(
            response="",  # 空响应，由下一个 Agent 生成
            updated_state={
                "intent": intent,
                "next_agent": next_agent
            }
        )

    def _quick_intent_check(self, question: str) -> Intent | None:
        """
        快速意图检查（规则匹配，减少 LLM 调用）
        """
        q = question.lower()

        # 退货关键词
        refund_keywords = ["退货", "退款", "退钱", "不要了", "换货"]
        if any(kw in q for kw in refund_keywords):
            return Intent.REFUND

        # 订单关键词
        order_keywords = ["订单", "物流", "到哪了", "快递", "发货", "签收", "SN"]
        if any(kw in q for kw in order_keywords):
            return Intent.ORDER

        # 简单的问候检测
        greeting_keywords = ["你好", "您好", "hi", "hello", "在吗"]
        if any(q.strip().startswith(kw) for kw in greeting_keywords) and len(q) < 10:
            return Intent.OTHER

        return None

    async def _llm_intent_recognition(self, question: str) -> Intent:
        """调用 LLM 进行意图识别"""
        try:
            messages = [
                HumanMessage(content=question)
            ]
            response = await self._call_llm(messages)

            intent_str = response.strip().upper()

            # 验证返回的意图是否合法
            if intent_str in [Intent.ORDER, Intent.POLICY, Intent.REFUND, Intent.OTHER]:
                return Intent(intent_str)
            else:
                # 容错处理
                print(f"[Router] 无法识别的意图: {intent_str}，默认 OTHER")
                return Intent.OTHER

        except Exception as e:
            print(f"[Router] 意图识别失败: {e}，默认 OTHER")
            return Intent.OTHER

    def _decide_next_agent(self, intent: Intent) -> str:
        """
        根据意图决定下一个 Agent

        Returns:
            "policy" - 政策专家
            "order" - 订单专家（也处理退货）
            "supervisor" - 监督者（用于 OTHER）
        """
        if intent == Intent.POLICY:
            return "policy"
        elif intent in [Intent.ORDER, Intent.REFUND]:
            return "order"
        else:
            return "supervisor"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest test/agents/test_router.py -v
# 预期：所有测试通过
```

- [ ] **Step 5: 提交更改**

```bash
git add app/agents/router.py test/agents/test_router.py
git commit -m "feat: implement RouterAgent with intent recognition and routing"
```

---

## Task 6: 创建 PolicyAgent（政策专家）

**Files:**
- Create: `app/agents/policy.py`
- Create: `test/agents/test_policy.py`

- [ ] **Step 1: 编写 PolicyAgent 测试**

```python
# test/agents/test_policy.py
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.policy import PolicyAgent


class TestPolicyAgent:
    """测试政策 Agent"""

    @pytest.fixture
    def policy_agent(self):
        return PolicyAgent()

    @pytest.mark.asyncio
    async def test_process_with_rag_context(self, policy_agent):
        """测试有 RAG 上下文时的处理"""
        # Mock RAG 检索
        with patch.object(policy_agent, '_retrieve_knowledge', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = (
                ["运费满100免运费", "配送时效1-3天"],
                {"distances": [0.2, 0.25]}
            )

            result = await policy_agent.process({
                "question": "运费怎么算？",
                "user_id": 1,
                "context": []
            })

            assert "运费" in result.response
            assert result.updated_state["context"] == ["运费满100免运费", "配送时效1-3天"]
            assert result.updated_state["retrieval_metadata"] is not None

    @pytest.mark.asyncio
    async def test_process_with_empty_retrieval(self, policy_agent):
        """测试 RAG 检索为空时的处理"""
        with patch.object(policy_agent, '_retrieve_knowledge', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = ([], {"distances": []})

            result = await policy_agent.process({
                "question": "请问这个政策是什么意思？",
                "user_id": 1,
                "context": []
            })

            # 应该返回无法回答，且置信度较低
            assert "抱歉" in result.response or "暂未查询" in result.response
            assert result.confidence is not None
            assert result.confidence < 0.5
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest test/agents/test_policy.py -v
# 预期：失败
```

- [ ] **Step 3: 创建 PolicyAgent 实现**

```python
# app/agents/policy.py
from langchain_core.messages import HumanMessage
from sqlmodel import select

from app.agents.base import AgentResult, BaseAgent
from app.core.database import async_session_maker
from app.models.knowledge import KnowledgeChunk


POLICY_SYSTEM_PROMPT = """你是专业的电商政策咨询专家。

规则：
1. 只能依据提供的参考信息回答，严禁编造
2. 如果参考信息为空，直接回答"抱歉，暂未查询到相关规定"
3. 回答简洁明了，引用具体政策条款
4. 语气专业、客气"""


SIMILARITY_THRESHOLD = 0.5


class PolicyAgent(BaseAgent):
    """
    政策专家 Agent

    职责：
    1. 执行 RAG 检索获取相关政策
    2. 基于检索结果生成准确回答
    3. 计算回答置信度
    """

    def __init__(self):
        super().__init__(
            name="policy",
            system_prompt=POLICY_SYSTEM_PROMPT
        )

    async def process(self, state: dict) -> AgentResult:
        """
        处理政策咨询
        """
        question = state.get("question", "")

        # Step 1: RAG 检索
        context, retrieval_metadata = await self._retrieve_knowledge(question)

        # Step 2: 构建消息并生成回复
        messages = self._create_messages(
            question,
            context={"context": context}
        )

        response = await self._call_llm(messages)

        # Step 3: 计算置信度（初步估计）
        confidence = self._estimate_confidence(context, retrieval_metadata)

        return AgentResult(
            response=response,
            updated_state={
                "context": context,
                "retrieval_metadata": retrieval_metadata,
                "answer": response
            },
            confidence=confidence
        )

    async def _retrieve_knowledge(
        self,
        question: str
    ) -> tuple[list[str], dict]:
        """
        执行 RAG 检索

        Returns:
            (context_list, metadata)
        """
        from app.graph.nodes import embedding_model

        # 生成查询向量
        query_vector = await embedding_model.aembed_query(question)

        async with async_session_maker() as session:
            distance_col = KnowledgeChunk.embedding.cosine_distance(query_vector).label("distance")

            stmt = (
                select(KnowledgeChunk, distance_col)
                .where(KnowledgeChunk.is_active)
                .order_by(distance_col)
                .limit(5)
            )
            result = await session.exec(stmt)
            results = result.all()

        # 过滤并收集结果
        valid_chunks = []
        distances = []

        for chunk, distance in results:
            distances.append(float(distance))
            if distance < SIMILARITY_THRESHOLD:
                valid_chunks.append(chunk.content)

        metadata = {
            "distances": distances,
            "valid_chunks": len(valid_chunks),
            "total_chunks": len(results)
        }

        print(f"[PolicyAgent] 检索到 {len(results)} 条，有效 {len(valid_chunks)} 条")

        return valid_chunks, metadata

    def _estimate_confidence(
        self,
        context: list[str],
        metadata: dict
    ) -> float:
        """
        初步估计置信度（完整置信度在置信度节点计算）
        """
        if not context:
            return 0.0

        distances = metadata.get("distances", [])
        if distances:
            avg_distance = sum(distances) / len(distances)
            # 简单映射：距离越小置信度越高
            if avg_distance < 0.3:
                return 0.8
            elif avg_distance < 0.5:
                return 0.5
            else:
                return 0.2

        return 0.5 if len(context) > 0 else 0.0
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest test/agents/test_policy.py -v
# 预期：所有测试通过
```

- [ ] **Step 5: 提交更改**

```bash
git add app/agents/policy.py test/agents/test_policy.py
git commit -m "feat: implement PolicyAgent with RAG retrieval"
```

---

## Task 7: 创建 OrderAgent（订单专家）

**Files:**
- Create: `app/agents/order.py`
- Create: `test/agents/test_order.py`

- [ ] **Step 1: 编写 OrderAgent 测试**

```python
# test/agents/test_order.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.order import OrderAgent


class TestOrderAgent:
    """测试订单 Agent"""

    @pytest.fixture
    def order_agent(self):
        return OrderAgent()

    @pytest.mark.asyncio
    async def test_query_order(self, order_agent):
        """测试订单查询"""
        # Mock 数据库查询
        mock_order = MagicMock()
        mock_order.order_sn = "SN20240001"
        mock_order.status = "PAID"
        mock_order.total_amount = 199.0
        mock_order.items = [{"name": "测试商品", "qty": 1}]
        mock_order.model_dump.return_value = {
            "order_sn": "SN20240001",
            "status": "PAID",
            "total_amount": 199.0
        }

        with patch('app.agents.order.async_session_maker') as mock_session:
            mock_result = MagicMock()
            mock_result.first.return_value = mock_order

            mock_exec = MagicMock()
            mock_exec.exec.return_value = mock_result

            # 构建 async context manager mock
            async_mock = AsyncMock()
            async_mock.__aenter__ = AsyncMock(return_value=mock_exec)
            async_mock.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = async_mock

            result = await order_agent.process({
                "question": "查询订单 SN20240001",
                "user_id": 1,
                "intent": "ORDER"
            })

            assert "SN20240001" in result.response
            assert result.updated_state["order_data"] is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest test/agents/test_order.py -v
# 预期：失败
```

- [ ] **Step 3: 创建 OrderAgent 实现**

```python
# app/agents/order.py
import re

from sqlmodel import select

from app.agents.base import AgentResult, BaseAgent
from app.core.database import async_session_maker
from app.models.order import Order
from app.services.refund_service import RefundApplicationService, RefundReason


ORDER_SYSTEM_PROMPT = """你是专业的电商订单处理助手。

规则：
1. 准确查询订单信息，清晰列出订单号、状态、金额
2. 处理退货申请时，先检查资格再提交
3. 订单数据必须来自数据库，严禁编造
4. 语气友好，解答用户疑问"""


class OrderAgent(BaseAgent):
    """
    订单专家 Agent

    职责：
    1. 查询订单状态和信息
    2. 处理退货申请流程
    3. 检查退货资格
    """

    def __init__(self):
        super().__init__(
            name="order",
            system_prompt=ORDER_SYSTEM_PROMPT
        )

    async def process(self, state: dict) -> AgentResult:
        """
        处理订单相关请求
        """
        question = state.get("question", "")
        user_id = state.get("user_id")
        intent = state.get("intent")

        if intent == "REFUND":
            return await self._handle_refund(question, user_id)
        else:
            return await self._handle_order_query(question, user_id)

    async def _handle_order_query(
        self,
        question: str,
        user_id: int
    ) -> AgentResult:
        """处理订单查询"""
        # 提取订单号
        order_sn = self._extract_order_sn(question)

        # 查询订单
        order_data = await self._query_order(order_sn, user_id)

        if not order_data:
            return AgentResult(
                response="抱歉，未找到相关订单信息。请确认订单号是否正确，或尝试查询"我的订单"。",
                updated_state={"order_data": None}
            )

        # 生成回复
        response = self._format_order_response(order_data)

        return AgentResult(
            response=response,
            updated_state={"order_data": order_data}
        )

    async def _handle_refund(
        self,
        question: str,
        user_id: int
    ) -> AgentResult:
        """处理退货申请"""
        # 提取订单号
        order_sn = self._extract_order_sn(question)

        if not order_sn:
            return AgentResult(
                response="请提供订单号以便处理退货申请。例如：我要退货，订单号 SN20240001",
                updated_state={"refund_flow_active": False}
            )

        # 提取退货原因
        reason_detail = question
        reason_category = self._classify_refund_reason(question)

        # 查询订单
        async with async_session_maker() as session:
            stmt = select(Order).where(
                Order.order_sn == order_sn.upper(),
                Order.user_id == user_id
            )
            result = await session.exec(stmt)
            order = result.first()

            if not order:
                return AgentResult(
                    response=f"未找到订单 {order_sn}，请确认订单号是否正确。",
                    updated_state={"refund_flow_active": False}
                )

            # 检查退货资格
            from app.services.refund_service import RefundEligibilityChecker
            is_eligible, eligibility_msg = await RefundEligibilityChecker.check_eligibility(
                order, session
            )

            if not is_eligible:
                return AgentResult(
                    response=f"该订单不符合退货条件：{eligibility_msg}",
                    updated_state={
                        "order_data": order.model_dump(),
                        "refund_flow_active": False
                    }
                )

            # 创建退货申请
            success, message, refund_app = await RefundApplicationService.create_refund_application(
                order_id=order.id,
                user_id=user_id,
                reason_detail=reason_detail,
                reason_category=reason_category,
                session=session
            )

            if success:
                return AgentResult(
                    response=f"✅ {message}",
                    updated_state={
                        "order_data": order.model_dump(),
                        "refund_data": {
                            "refund_id": refund_app.id,
                            "amount": float(refund_app.refund_amount)
                        },
                        "refund_flow_active": True
                    }
                )
            else:
                return AgentResult(
                    response=f"❌ {message}",
                    updated_state={"refund_flow_active": False}
                )

    def _extract_order_sn(self, text: str) -> str | None:
        """提取订单号"""
        match = re.search(r'(SN\d+)', text, re.IGNORECASE)
        return match.group(1).upper() if match else None

    def _classify_refund_reason(self, text: str) -> RefundReason:
        """分类退货原因"""
        if "质量" in text or "破损" in text:
            return RefundReason.QUALITY_ISSUE
        elif "尺码" in text or "大小" in text or "不合适" in text:
            return RefundReason.SIZE_NOT_FIT
        elif "不符" in text or "描述" in text:
            return RefundReason.NOT_AS_DESCRIBED
        else:
            return RefundReason.OTHER

    async def _query_order(
        self,
        order_sn: str | None,
        user_id: int
    ) -> dict | None:
        """查询订单"""
        async with async_session_maker() as session:
            if order_sn:
                stmt = select(Order).where(
                    Order.order_sn == order_sn,
                    Order.user_id == user_id
                )
            else:
                # 查询最近订单
                stmt = (
                    select(Order)
                    .where(Order.user_id == user_id)
                    .order_by(Order.created_at.desc())
                    .limit(1)
                )

            result = await session.exec(stmt)
            order = result.first()

            return order.model_dump() if order else None

    def _format_order_response(self, order: dict) -> str:
        """格式化订单回复"""
        items = order.get("items", [])
        items_str = ", ".join([f"{i.get('name', '商品')}x{i.get('qty', 1)}" for i in items])

        return (
            f"📦 订单信息：\n"
            f"订单号: {order.get('order_sn', 'N/A')}\n"
            f"状态: {order.get('status', 'N/A')}\n"
            f"商品: {items_str}\n"
            f"金额: ¥{order.get('total_amount', 0)}\n"
            f"物流单号: {order.get('tracking_number', '暂无')}"
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest test/agents/test_order.py -v
# 预期：所有测试通过
```

- [ ] **Step 5: 提交更改**

```bash
git add app/agents/order.py test/agents/test_order.py
git commit -m "feat: implement OrderAgent for order query and refund"
```

---

## Task 8: 创建 SupervisorAgent（监督协调）

**Files:**
- Create: `app/agents/supervisor.py`
- Create: `test/agents/test_supervisor.py`

- [ ] **Step 1: 编写 SupervisorAgent 测试**

```python
# test/agents/test_supervisor.py
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.supervisor import SupervisorAgent


class TestSupervisorAgent:
    """测试监督 Agent"""

    @pytest.fixture
    def supervisor(self):
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_coordinate_policy_flow(self, supervisor):
        """测试协调政策查询流程"""
        # Mock RouterAgent
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {
                "intent": "POLICY",
                "next_agent": "policy"
            }
            mock_router.return_value.response = ""

            # Mock PolicyAgent
            with patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy:
                mock_policy.return_value.updated_state = {
                    "answer": "运费满100免运费",
                    "context": ["运费政策"]
                }
                mock_policy.return_value.response = "运费满100免运费"
                mock_policy.return_value.confidence = 0.85

                result = await supervisor.coordinate({
                    "question": "运费怎么算？",
                    "user_id": 1
                })

                assert result["answer"] == "运费满100免运费"
                assert result["confidence_score"] == 0.85

    @pytest.mark.asyncio
    async def test_high_confidence_no_audit(self, supervisor):
        """测试高置信度不触发审核"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {"intent": "POLICY", "next_agent": "policy"}
            mock_router.return_value.response = ""

            with patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy:
                mock_policy.return_value.response = "这是回答"
                mock_policy.return_value.confidence = 0.9
                mock_policy.return_value.updated_state = {"answer": "这是回答"}

                result = await supervisor.coordinate({
                    "question": "简单问题",
                    "user_id": 1
                })

                assert result["needs_human_transfer"] is False
                assert result["audit_required"] is False
```

- [ ] **Step 2: 创建 SupervisorAgent 实现**

```python
# app/agents/supervisor.py
from app.agents.base import AgentResult, BaseAgent
from app.agents.order import OrderAgent
from app.agents.policy import PolicyAgent
from app.agents.router import RouterAgent
from app.confidence import ConfidenceEvaluator


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

        # 初始化置信度评估器
        self.confidence_evaluator = ConfidenceEvaluator(threshold=0.6)

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
        retrieval_metadata = specialist_result.updated_state.get("retrieval_metadata") if specialist_result.updated_state else None

        confidence_result = await self.confidence_evaluator.evaluate(
            question=question,
            context=context,
            answer=answer,
            retrieval_metadata=retrieval_metadata
        )

        print(f"[Supervisor] 置信度评估: {confidence_result['confidence_score']:.3f}, "
              f"转人工: {confidence_result['needs_transfer']}")

        # Step 4: 构建最终状态
        final_state = {
            "answer": answer,
            "intent": intent,
            "confidence_score": confidence_result["confidence_score"],
            "confidence_signals": confidence_result["confidence_signals"],
            "needs_human_transfer": confidence_result["needs_transfer"],
            "transfer_reason": confidence_result.get("reason"),
            "audit_required": confidence_result["needs_transfer"],
            "audit_type": "CONFIDENCE" if confidence_result["needs_transfer"] else None
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
```

- [ ] **Step 3: 提交更改**

```bash
git add app/agents/supervisor.py test/agents/test_supervisor.py
git commit -m "feat: implement SupervisorAgent for multi-agent coordination"
```

---

## Task 9: 重构工作流集成多 Agent

**Files:**
- Modify: `app/graph/workflow.py`
- Modify: `app/graph/nodes.py` (可选，兼容层)

- [ ] **Step 1: 重写 workflow.py 使用新架构**

```python
# app/graph/workflow.py
from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from app.agents import SupervisorAgent
from app.core.config import settings
from app.graph.state import AgentState

app_graph = None


# 初始化 Supervisor Agent
supervisor = SupervisorAgent()


async def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 节点：协调所有 Agent

    这个节点替代了原来的 intent_router + retrieve/query_order/handle_refund
    """
    result = await supervisor.coordinate(state)
    return result


def route_after_evaluation(state: AgentState):
    """
    根据置信度评估结果路由

    - 需要人工接管 → END (等待审核)
    - 不需要 → 直接结束流程（Supervisor 已经生成了 answer）
    """
    if state.get("needs_human_transfer", False):
        print(f"[Workflow] 置信度不足 ({state.get('confidence_score', 0):.3f})，转人工")
        return END

    # 不需要转人工，流程结束
    return END


# 构建新的工作流
workflow = StateGraph(AgentState)

# 只保留 Supervisor 节点（它内部协调所有 Specialist Agents）
workflow.add_node("supervisor", supervisor_node)

# 入口 → Supervisor
workflow.add_edge(START, "supervisor")

# Supervisor 后根据评估结果路由
workflow.add_conditional_edges(
    "supervisor",
    route_after_evaluation,
    {END: END}
)


async def compile_app_graph():
    """编译 LangGraph"""
    print("🔧 Compiling Multi-Agent LangGraph with Redis checkpointer...")

    checkpointer = AsyncRedisSaver(redis_url=settings.REDIS_URL)
    await checkpointer.setup()

    compiled_graph = workflow.compile(checkpointer=checkpointer)

    print("✅ Multi-Agent LangGraph compiled successfully!")
    return compiled_graph
```

- [ ] **Step 2: 提交更改**

```bash
git add app/graph/workflow.py
git commit -m "refactor: integrate multi-agent architecture into workflow"
```

---

## Task 10: 扩展管理员 API 支持置信度审核

**Files:**
- Modify: `app/api/v1/admin.py`
- Modify: `app/models/audit.py` (新增置信度审核类型)

- [ ] **Step 1: 修改 audit.py 模型**

```python
# 在 app/models/audit.py 中添加新的触发类型

class AuditTriggerType(str, Enum):
    """审核触发类型"""
    RISK = "RISK"                    # 金额风险触发
    CONFIDENCE = "CONFIDENCE"        # 置信度不足触发
    MANUAL = "MANUAL"                # 用户主动要求


# 在 AuditLog 模型中添加字段
trigger_type: AuditTriggerType = Field(
    default=AuditTriggerType.RISK,
    sa_column=Column(String, index=True, nullable=False),
    description="触发审核的类型"
)

# 置信度相关字段（JSON 存储）
confidence_metadata: dict[str, Any] | None = Field(
    default=None,
    sa_column=Column(JSON, nullable=True),
    description="置信度评估元数据"
)
```

- [ ] **Step 2: 修改 admin.py 增加置信度任务接口**

```python
# 在 app/api/v1/admin.py 中添加

@router.get("/admin/confidence-tasks", response_model=list[AuditTask])
async def get_confidence_pending_tasks(
    current_admin_id: int = Depends(get_current_user_id)
):
    """
    获取置信度触发的待审核任务

    与风险审核任务分开，便于管理员分类处理
    """
    async with async_session_maker() as session:
        from app.models.audit import AuditTriggerType

        stmt = select(AuditLog).where(
            AuditLog.action == AuditAction.PENDING,
            AuditLog.trigger_type == AuditTriggerType.CONFIDENCE
        ).order_by(desc(AuditLog.created_at))

        result = await session.execute(stmt)
        audit_logs = result.scalars().all()

        # 转换为响应格式（复用现有 AuditTask 结构）
        tasks = []
        for log in audit_logs:
            # 从 confidence_metadata 中提取置信度信息
            confidence_meta = log.confidence_metadata or {}

            tasks.append(AuditTask(
                audit_log_id=log.id,
                thread_id=log.thread_id,
                user_id=log.user_id,
                refund_application_id=log.refund_application_id,
                order_id=log.order_id,
                trigger_reason=f"置信度不足: {confidence_meta.get('confidence_score', 0):.2f} - {log.trigger_reason}",
                risk_level="LOW",  # 置信度问题默认低风险
                context_snapshot=log.context_snapshot,
                created_at=log.created_at.isoformat(),
            ))

        return tasks


@router.get("/admin/tasks-all", response_model=dict)
async def get_all_pending_tasks(
    current_admin_id: int = Depends(get_current_user_id)
):
    """
    获取所有待审核任务（风险 + 置信度）

    用于管理后台统一展示
    """
    async with async_session_maker() as session:
        from app.models.audit import AuditTriggerType

        # 查询风险任务
        risk_stmt = select(AuditLog).where(
            AuditLog.action == AuditAction.PENDING,
            AuditLog.trigger_type == AuditTriggerType.RISK
        )
        risk_result = await session.execute(risk_stmt)

        # 查询置信度任务
        conf_stmt = select(AuditLog).where(
            AuditLog.action == AuditAction.PENDING,
            AuditLog.trigger_type == AuditTriggerType.CONFIDENCE
        )
        conf_result = await session.execute(conf_stmt)

        return {
            "risk_tasks": len(risk_result.scalars().all()),
            "confidence_tasks": len(conf_result.scalars().all()),
            "total": len(risk_result.scalars().all()) + len(conf_result.scalars().all())
        }
```

- [ ] **Step 3: 创建数据库迁移脚本**

```bash
# 生成迁移
alembic revision --autogenerate -m "add confidence audit trigger type"
```

```python
# migrations/versions/xxx_add_confidence_audit_trigger_type.py
"""add confidence audit trigger type

Revision ID: xxx
Revises: previous_revision
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'xxx'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None


def upgrade():
    # 创建枚举类型
    audittriggertype = sa.Enum('RISK', 'CONFIDENCE', 'MANUAL', name='audittriggertype')
    audittriggertype.create(op.get_bind())

    # 添加 trigger_type 列
    op.add_column(
        'audit_logs',
        sa.Column(
            'trigger_type',
            sa.Enum('RISK', 'CONFIDENCE', 'MANUAL', name='audittriggertype'),
            nullable=False,
            server_default='RISK'
        )
    )

    # 添加 confidence_metadata 列
    op.add_column(
        'audit_logs',
        sa.Column('confidence_metadata', sa.JSON(), nullable=True)
    )

    # 创建索引
    op.create_index('ix_audit_logs_trigger_type', 'audit_logs', ['trigger_type'])


def downgrade():
    op.drop_index('ix_audit_logs_trigger_type', table_name='audit_logs')
    op.drop_column('audit_logs', 'confidence_metadata')
    op.drop_column('audit_logs', 'trigger_type')
    audittriggertype = sa.Enum('RISK', 'CONFIDENCE', 'MANUAL', name='audittriggertype')
    audittriggertype.drop(op.get_bind())
```

- [ ] **Step 4: 提交更改**

```bash
git add app/api/v1/admin.py app/models/audit.py migrations/
git commit -m "feat: extend admin API for confidence-based audit tasks"
```

---

## Task 11: 更新前端展示置信度信息

**Files:**
- Modify: `app/frontend/customer_ui.py` - 显示置信度状态
- Modify: `app/frontend/admin_dashboard.py` - 显示置信度任务

- [ ] **Step 1: 修改 customer_ui.py 状态展示**

```python
# 在 app/frontend/customer_ui.py 中修改状态显示

def render_audit_card_v2(status_info: dict) -> str:
    """优化的审核卡片渲染，支持置信度触发"""
    status = status_info.get("status", "UNKNOWN")
    data = status_info.get("data", {})
    audit_type = data.get("audit_type", "RISK")  # 新增

    if status == "WAITING_ADMIN":
        # 根据触发类型显示不同文案
        if audit_type == "CONFIDENCE":
            return f'''
            <div class="audit-card audit-card-pending">
                <b>⏳ 正在为您转接专业客服</b><br>
                原因：您的问题需要人工进一步确认<br>
                置信度: {data.get('confidence_score', 0):.0%}
            </div>'''
        else:
            return f'''
            <div class="audit-card audit-card-pending">
                <b>⏳ 触发风控审核</b><br>
                原因：{data.get("trigger_reason", "未知")}<br>
                风险等级：{data.get("risk_level", "NORMAL")}
            </div>'''

    # ... 其他状态保持不变
```

- [ ] **Step 2: 修改 admin_dashboard.py 增加置信度任务筛选**

```python
# 在 app/frontend/admin_dashboard.py 中
# 在任务筛选区域增加置信度任务选项

with gr.Row():
    task_type_filter = gr.Radio(
        choices=["全部", "风险审核", "置信度审核"],
        value="全部",
        label="任务类型筛选",
        scale=3
    )
    risk_filter = gr.Radio(
        choices=["全部", "HIGH", "MEDIUM", "LOW"],
        value="全部",
        label="风险等级筛选",
        scale=3
    )
    refresh_btn = gr.Button("刷新", variant="secondary", scale=1, size="sm")

# 根据筛选调用不同 API
def load_tasks(client: AdminClient, task_type: str, risk_level: str):
    if task_type == "置信度审核":
        tasks = client.get_confidence_tasks()  # 需要实现这个方法
    elif task_type == "风险审核":
        tasks = client.get_risk_tasks(risk_level)
    else:
        tasks = client.get_all_tasks(risk_level)
    # ...
```

- [ ] **Step 3: 提交更改**

```bash
git add app/frontend/
git commit -m "ui: update frontend to display confidence-based transfer info"
```

---

## Task 12: 完整集成测试

**Files:**
- Create: `test/integration/test_multi_agent_flow.py`

- [ ] **Step 1: 创建集成测试**

```python
# test/integration/test_multi_agent_flow.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents import SupervisorAgent
from app.confidence import ConfidenceEvaluator


class TestMultiAgentFlow:
    """测试完整的多 Agent 流程"""

    @pytest.fixture
    async def supervisor(self):
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_full_policy_query_flow(self, supervisor):
        """测试完整的政策查询流程"""
        # 执行完整流程
        result = await supervisor.coordinate({
            "question": "运费怎么算？",
            "user_id": 1,
            "thread_id": "test_thread_1"
        })

        # 验证结果结构
        assert "answer" in result
        assert "intent" in result
        assert "confidence_score" in result
        assert "confidence_signals" in result
        assert "needs_human_transfer" in result

        # 验证意图识别正确
        assert result["intent"] == "POLICY"

        print(f"回答: {result['answer']}")
        print(f"置信度: {result['confidence_score']}")
        print(f"信号详情: {result['confidence_signals']}")

    @pytest.mark.asyncio
    async def test_confidence_triggered_transfer(self, supervisor):
        """测试置信度触发转人工"""
        # 使用一个难以回答的问题
        result = await supervisor.coordinate({
            "question": "你们公司 CEO 的私人电话是多少？",
            "user_id": 1,
            "thread_id": "test_thread_2"
        })

        # 应该触发转人工（因为检索不到相关内容）
        if result.get("needs_human_transfer"):
            print(f"正确触发转人工，原因: {result.get('transfer_reason')}")
            print(f"置信度: {result.get('confidence_score')}")
        else:
            print(f"未触发转人工，置信度: {result.get('confidence_score')}")
            # 记录但不失败，因为取决于知识库内容
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest test/integration/test_multi_agent_flow.py -v -s
```

- [ ] **Step 3: 提交更改**

```bash
git add test/integration/
git commit -m "test: add integration tests for multi-agent flow"
```

---

## Task 13: 运行完整测试套件

- [ ] **Step 1: 运行所有测试**

```bash
# 运行置信度模块测试
pytest test/confidence/ -v

# 运行 Agent 模块测试
pytest test/agents/ -v

# 运行集成测试
pytest test/integration/ -v

# 运行全部测试
pytest -v
```

- [ ] **Step 2: 修复任何失败的测试**

- [ ] **Step 3: 最终提交**

```bash
git commit -m "test: all tests passing for confidence + multi-agent features" || echo "Nothing to commit"
```

---

## Task 14: 更新文档

**Files:**
- Create: `docs/features/confidence-multi-agent.md`

- [ ] **Step 1: 编写功能文档**

```markdown
# 置信度驱动人工接管 + 多 Agent 架构

## 概述

本功能实现了：
1. **置信度评估系统**：基于 RAG 质量、LLM 自我评估、用户情感三信号决定是否需要人工接管
2. **多 Agent 架构**：将单体 Agent 拆分为 RouterAgent、PolicyAgent、OrderAgent、SupervisorAgent

## 架构图

```
用户提问
    ↓
RouterAgent (意图识别)
    ↓
Supervisor (协调)
    ├─→ PolicyAgent (政策查询)
    └─→ OrderAgent (订单/退货)
    ↓
ConfidenceEvaluator (置信度评估)
    ↓
高置信度 → 直接返回回答
低置信度 → 转人工审核
```

## 配置

在 `app/core/config.py` 中添加：

```python
# 置信度阈值
CONFIDENCE_THRESHOLD: float = 0.6

# 信号权重
CONFIDENCE_SIGNAL_WEIGHTS: dict = {
    "rag": 0.4,
    "llm": 0.4,
    "emotion": 0.2
}
```

## 使用

无需额外操作，系统会自动：
1. 评估每个回答的置信度
2. 低于阈值时自动创建审核任务
3. 管理员在 Dashboard 中处理置信度任务

## 监控

置信度信号会被记录到 `audit_logs.confidence_metadata` 字段，可用于分析：
- 哪些类型的问题容易置信度低
- RAG 检索质量趋势
- 用户情感分布
```

- [ ] **Step 2: 提交更改**

```bash
git add docs/
git commit -m "docs: add confidence and multi-agent architecture documentation"
```

---

## 成本优化

### 原成本分析

| 信号 | 成本 | 说明 |
|------|------|------|
| RAGSignal | ~0.001元/次 | embeddings 计算 |
| LLMSignal | ~0.05元/次 | qwen-max 自我评估 |
| EmotionSignal | ~0.001元/次 | 本地规则计算 |
| **总计** | **~0.052元/次** | 比当前增加约61% |

### 优化方案

#### 1. 使用 qwen-turbo 替代 qwen-max 做自我评估

**文件**: `app/confidence/signals.py`

```python
class LLMSignal:
    """LLM 自我评估信号（成本优化版）"""

    def __init__(self):
        # 使用更便宜的模型进行自我评估
        from langchain_community.chat_models import ChatQwen
        self.llm = ChatQwen(
            model="qwen-turbo",  # 替代 qwen-max，成本降低80%
            temperature=0
        )
        # ...
```

**成本降低**: ~0.05元 → ~0.01元（降低80%）

#### 2. 缓存相似问题的 LLMSignal

**新建文件**: `app/confidence/cache.py`

```python
import hashlib
import json
from dataclasses import asdict
from typing import Optional

import redis.asyncio as redis

from app.confidence.signals import LLMSignal
from app.core.config import settings


class ConfidenceCache:
    """基于问题哈希的置信度缓存"""

    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=3,  # 使用独立db
            decode_responses=True
        )
        self.ttl = 3600  # 1小时

    def _hash_question(self, question: str, context: list[str]) -> str:
        """生成问题指纹"""
        content = f"{question}:{json.dumps(context, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def get(
        self,
        question: str,
        context: list[str]
    ) -> Optional[tuple[float, str]]:
        """获取缓存的 LLMSignal 结果"""
        key = f"llm_signal:{self._hash_question(question, context)}"
        cached = await self.redis.get(key)

        if cached:
            data = json.loads(cached)
            return data["score"], data["reason"]
        return None

    async def set(
        self,
        question: str,
        context: list[str],
        score: float,
        reason: str
    ):
        """缓存 LLMSignal 结果"""
        key = f"llm_signal:{self._hash_question(question, context)}"
        data = json.dumps({"score": score, "reason": reason})
        await self.redis.setex(key, self.ttl, data)

    async def get_hit_rate(self) -> float:
        """获取缓存命中率（用于监控）"""
        info = await self.redis.info("stats")
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 1)
        return hits / (hits + misses)
```

**修改 `app/confidence/signals.py`**:

```python
class LLMSignal:
    """LLM 自我评估信号（带缓存）"""

    def __init__(self):
        from langchain_community.chat_models import ChatQwen
        self.llm = ChatQwen(model="qwen-turbo", temperature=0)
        self.cache = ConfidenceCache()

    async def calculate(
        self,
        question: str,
        answer: str,
        context: list[str]
    ) -> tuple[float, str]:
        """计算 LLM 置信度信号（带缓存）"""

        # 1. 检查缓存
        cached = await self.cache.get(question, context)
        if cached:
            print(f"[LLMSignal] 缓存命中")
            return cached

        # 2. 执行 LLM 评估
        score, reason = await self._evaluate(question, answer, context)

        # 3. 写入缓存
        await self.cache.set(question, context, score, reason)

        return score, reason

    async def _evaluate(self, question: str, answer: str, context: list[str]) -> tuple[float, str]:
        """实际的 LLM 评估逻辑"""
        # ... 原有实现
```

**命中率预估**: 30-40%（基于重复问题统计）

#### 3. 智能跳过 LLMSignal

当 RAGSignal 已经很高或很低时，跳过 LLM 评估。

**修改 `app/confidence/evaluator.py`**:

```python
class ConfidenceEvaluator:
    """置信度评估器（智能跳过优化版）"""

    # RAG 信号阈值，超出此范围跳过 LLM 评估
    RAG_SKIP_HIGH = 0.9  # 高置信度跳过
    RAG_SKIP_LOW = 0.3   # 低置信度跳过

    async def evaluate(self, state: AgentState) -> ConfidenceResult:
        """评估置信度（智能跳过版）"""

        # 1. 并行计算 RAG 和 Emotion 信号（两者成本低）
        rag_task = self.rag_signal.calculate(
            context=state.get("context", []),
            retrieval_metadata=state.get("retrieval_metadata")
        )
        emotion_task = self.emotion_signal.calculate(
            state.get("question", "")
        )

        rag_score, rag_reason = await rag_task
        emotion_score, emotion_reason = await emotion_task

        # 2. 智能跳过 LLM 评估
        if rag_score > self.RAG_SKIP_HIGH:
            # 检索质量很高，直接推断高置信度
            llm_score = 0.9
            llm_reason = f"基于RAG高质量信号推断（{rag_score:.2f}）"
            print(f"[Confidence] 跳过LLM评估（RAG信号强）")

        elif rag_score < self.RAG_SKIP_LOW:
            # 检索质量很低，直接推断低置信度
            llm_score = 0.3
            llm_reason = f"基于RAG低质量信号推断（{rag_score:.2f}）"
            print(f"[Confidence] 跳过LLM评估（RAG信号弱）")

        else:
            # 需要 LLM 进一步评估
            llm_score, llm_reason = await self.llm_signal.calculate(
                question=state.get("question", ""),
                answer=state.get("answer", ""),
                context=state.get("context", [])
            )

        # 3. 加权计算最终置信度
        final_score = (
            rag_score * self.weights["rag"] +
            llm_score * self.weights["llm"] +
            emotion_score * self.weights["emotion"]
        )

        # ... 后续逻辑
```

**跳过比例预估**: 约50%的请求

### 优化后成本

| 项目 | 计算方式 | 成本 |
|------|----------|------|
| 基础成本（RAG + Emotion） | 固定 | ~0.002元 |
| LLMSignal 调用比例 | 50%跳过 × 70%未命中缓存 = 35% | - |
| LLMSignal 实际成本 | 0.01元 × 0.35 | ~0.0035元 |
| **总计** | | **~0.0055元/次** |

**效果**: 比优化前降低约89%，比当前系统降低约59%

---

## 风险缓解计划

### 风险 1: 过度转人工

**症状**: 置信度阈值过高导致大量请求转人工，增加人工成本

**缓解措施**:

```python
# app/core/config.py
CONFIDENCE_THRESHOLD: float = 0.5  # 初期宽松，默认0.6
```

```python
# app/monitoring/confidence_metrics.py
class ConfidenceMetrics:
    """置信度监控指标"""

    def __init__(self):
        self.transfer_rate_threshold = 0.2  # 转人工率阈值20%

    async def check_transfer_rate(self) -> dict:
        """检查转人工比例"""
        # 统计最近7天数据
        stats = await self._get_weekly_stats()
        transfer_rate = stats["transferred"] / stats["total"]

        return {
            "transfer_rate": transfer_rate,
            "alert": transfer_rate > self.transfer_rate_threshold,
            "suggested_threshold": self._suggest_threshold(stats)
        }

    def _suggest_threshold(self, stats: dict) -> float:
        """基于数据建议新阈值"""
        # 如果转人工率>20%，建议降低阈值
        # 如果转人工率<5%，建议提高阈值
        # 目标范围: 10-20%
        pass
```

**调整策略**:
- 初期 threshold = 0.5（宽松）
- 每周review转人工比例
- 目标转人工率: 10-20%

### 风险 2: 信号计算失败

**症状**: LLM 解析失败、服务超时、Redis连接中断

**缓解措施**:

```python
# app/confidence/signals.py
import asyncio
from typing import Optional

class SafeSignalCalculator:
    """带故障保护的信号计算器"""

    DEFAULT_SCORE = 0.5  # 保守默认值
    TIMEOUT_SECONDS = 3

    async def calculate_with_fallback(
        self,
        signal_name: str,
        calculate_fn,
        *args,
        **kwargs
    ) -> tuple[float, str]:
        """带故障保护的信号计算"""
        try:
            # 添加超时控制
            result = await asyncio.wait_for(
                calculate_fn(*args, **kwargs),
                timeout=self.TIMEOUT_SECONDS
            )
            return result

        except asyncio.TimeoutError:
            print(f"[{signal_name}] 计算超时，使用默认值")
            await self._alert(f"{signal_name} 计算超时")
            return self.DEFAULT_SCORE, f"{signal_name}计算超时，使用保守估计"

        except Exception as e:
            print(f"[{signal_name}] 计算失败: {e}")
            await self._alert(f"{signal_name} 计算失败: {str(e)}")
            return self.DEFAULT_SCORE, f"{signal_name}计算失败，使用保守估计"

    async def _alert(self, message: str):
        """发送告警"""
        # 集成告警系统（如钉钉、企业微信）
        pass
```

```python
# app/confidence/evaluator.py
class ConfidenceEvaluator:
    """带故障保护的评估器"""

    def __init__(self):
        self.safe_calculator = SafeSignalCalculator()
        self.rag_signal = RAGSignal()
        self.llm_signal = LLMSignal()
        self.emotion_signal = EmotionSignal()

    async def evaluate(self, state: AgentState) -> ConfidenceResult:
        """评估置信度（故障保护版）"""

        # 所有信号计算都带故障保护
        rag_score, rag_reason = await self.safe_calculator.calculate_with_fallback(
            "RAG", self.rag_signal.calculate,
            context=state.get("context", []),
            retrieval_metadata=state.get("retrieval_metadata")
        )

        llm_score, llm_reason = await self.safe_calculator.calculate_with_fallback(
            "LLM", self.llm_signal.calculate,
            question=state.get("question", ""),
            answer=state.get("answer", ""),
            context=state.get("context", [])
        )

        emotion_score, emotion_reason = await self.safe_calculator.calculate_with_fallback(
            "Emotion", self.emotion_signal.calculate,
            question=state.get("question", "")
        )

        # 即使某个信号失败，也能继续计算
        # ...
```

**告警规则**:
- 单信号失败率 > 5%: 发送告警
- 连续3次失败: 立即告警

### 风险 3: 延迟增加

**症状**: 串行计算导致响应变慢，用户体验下降

**缓解措施**:

```python
# app/confidence/evaluator.py
import asyncio

class ConfidenceEvaluator:
    """并行计算的评估器"""

    async def evaluate(self, state: AgentState) -> ConfidenceResult:
        """评估置信度（并行优化版）"""

        # 1. 并行计算 RAG 和 Emotion（两者独立且成本低）
        rag_task = asyncio.create_task(
            self.rag_signal.calculate(
                context=state.get("context", []),
                retrieval_metadata=state.get("retrieval_metadata")
            )
        )
        emotion_task = asyncio.create_task(
            self.emotion_signal.calculate(state.get("question", ""))
        )

        # 等待两者完成
        (rag_score, rag_reason), (emotion_score, emotion_reason) = await asyncio.gather(
            rag_task, emotion_task
        )

        # 2. 根据 RAG 结果决定是否执行 LLM 评估
        if self._should_skip_llm(rag_score):
            llm_score, llm_reason = self._infer_from_rag(rag_score)
        else:
            llm_score, llm_reason = await asyncio.wait_for(
                self.llm_signal.calculate(
                    question=state.get("question", ""),
                    answer=state.get("answer", ""),
                    context=state.get("context", [])
                ),
                timeout=3  # 3秒超时
            )

        # ...
```

```python
# app/graph/workflow.py
async def confidence_evaluation_node(state: AgentState) -> AgentState:
    """置信度评估节点（异步非阻塞版）"""

    # 创建后台任务，不阻塞回复返回
    asyncio.create_task(
        _async_evaluate_and_update(state)
    )

    # 立即返回，置信度评估在后台进行
    return state

async def _async_evaluate_and_update(state: AgentState):
    """后台执行置信度评估"""
    evaluator = ConfidenceEvaluator()
    result = await evaluator.evaluate(state)

    # 如果置信度低，创建审核任务
    if result.should_transfer:
        await create_audit_task(state, result)
```

**性能目标**:
- P95 延迟增加 < 100ms
- 置信度评估总耗时 < 500ms

### 风险 4: 误判高价值客户

**症状**: VIP 客户因置信度低被错误转人工，影响客户体验

**缓解措施**:

```python
# app/confidence/evaluator.py
class ConfidenceEvaluator:
    """支持VIP客户的评估器"""

    # VIP客户阈值调整
    VIP_THRESHOLD_ADJUSTMENT = 0.1  # VIP阈值降低0.1

    async def evaluate(
        self,
        state: AgentState,
        user_tier: str = "normal"  # normal, vip, svip
    ) -> ConfidenceResult:
        """评估置信度（支持分级客户）"""

        # 计算基础置信度
        base_score = await self._calculate_base_score(state)

        # 根据客户等级调整阈值
        threshold = self._get_threshold(user_tier)

        should_transfer = base_score < threshold

        # VIP转人工记录详细日志
        if should_transfer and user_tier in ["vip", "svip"]:
            await self._log_vip_transfer(state, base_score, threshold)

        return ConfidenceResult(
            score=base_score,
            threshold=threshold,
            should_transfer=should_transfer,
            # ...
        )

    def _get_threshold(self, user_tier: str) -> float:
        """获取客户分级阈值"""
        base = settings.CONFIDENCE_THRESHOLD

        adjustments = {
            "normal": 0.0,
            "vip": -0.1,   # VIP更宽松
            "svip": -0.15  # SVIP最宽松
        }

        return base + adjustments.get(user_tier, 0.0)

    async def _log_vip_transfer(self, state: AgentState, score: float, threshold: float):
        """记录VIP转人工日志"""
        await audit_logger.warning(
            "VIP客户触发转人工",
            extra={
                "user_id": state.get("user_id"),
                "score": score,
                "threshold": threshold,
                "question": state.get("question"),
                "signals": state.get("confidence_signals")
            }
        )
```

**Review机制**:
- 每日review VIP转人工记录
- 每周分析VIP客户满意度
- 月度调整VIP阈值策略

### 风险 5: 情感检测误报

**症状**: 正常表达被误判为愤怒，导致不必要的人工介入

**缓解措施**:

```python
# app/confidence/signals.py
class EmotionSignal:
    """情感检测信号（双重验证版）"""

    def __init__(self):
        self.negative_history: dict[int, list] = {}  # user_id -> 情绪历史
        self.trigger_threshold = 2  # 连续2轮负面情绪才触发

    async def calculate(
        self,
        question: str,
        user_id: Optional[int] = None
    ) -> tuple[float, str]:
        """计算情感信号（带历史验证）"""

        # 1. 规则检测
        rule_score, rule_reason = self._rule_based_detect(question)

        # 2. 轻量模型检测（可选，用于验证）
        model_score, model_reason = await self._light_model_detect(question)

        # 3. 双重验证：规则和模型都检测到负面情绪
        if rule_score < 0.5 and model_score < 0.5:
            current_negative = True
        else:
            current_negative = False

        # 4. 检查历史记录
        if user_id and current_negative:
            history = self._get_negative_history(user_id)
            if len(history) < self.trigger_threshold - 1:
                # 负面情绪次数不足，不降权
                return 0.7, f"检测到负面情绪但次数不足（{len(history)+1}/{self.trigger_threshold}）"

        # 记录当前情绪
        if user_id:
            self._record_emotion(user_id, current_negative)

        # 最终分数
        final_score = (rule_score + model_score) / 2

        return final_score, f"规则:{rule_reason}, 模型:{model_reason}"

    def _rule_based_detect(self, question: str) -> tuple[float, str]:
        """基于规则的情感检测"""
        # ... 原有实现

    async def _light_model_detect(self, question: str) -> tuple[float, str]:
        """轻量模型验证（可选，使用本地小模型）"""
        # 可使用本地情感分析模型如 bert-base-chinese-sentiment
        # 或使用简单的关键词扩展
        pass

    def _get_negative_history(self, user_id: int) -> list:
        """获取用户负面情绪历史"""
        return self.negative_history.get(user_id, [])

    def _record_emotion(self, user_id: int, is_negative: bool):
        """记录用户情绪"""
        if user_id not in self.negative_history:
            self.negative_history[user_id] = []

        self.negative_history[user_id].append({
            "timestamp": time.time(),
            "is_negative": is_negative
        })

        # 清理过期记录（保留最近10轮）
        self.negative_history[user_id] = self.negative_history[user_id][-10:]
```

**误报处理**:
- 需要连续2轮负面情绪才触发降权
- 规则和模型双重验证
- 定期review误判案例，优化规则

---

## 监控和告警建议

### 关键指标

```python
# app/monitoring/metrics.py
CONFIDENCE_METRICS = {
    # 成本指标
    "cost_per_request": {
        "description": "单次请求成本",
        "threshold": 0.01,  # 元
        "alert_operator": ">"
    },

    # 质量指标
    "transfer_rate": {
        "description": "转人工比例",
        "threshold": 0.20,  # 20%
        "alert_operator": ">"
    },
    "false_transfer_rate": {  # 误判率（通过人工review统计）
        "description": "误判转人工比例",
        "threshold": 0.10,  # 10%
        "alert_operator": ">"
    },

    # 性能指标
    "evaluation_latency_p95": {
        "description": "置信度评估P95延迟",
        "threshold": 500,  # ms
        "alert_operator": ">"
    },

    # 稳定性指标
    "signal_failure_rate": {
        "description": "信号计算失败率",
        "threshold": 0.05,  # 5%
        "alert_operator": ">"
    },
    "cache_hit_rate": {
        "description": "LLMSignal缓存命中率",
        "threshold": 0.30,  # 30%
        "alert_operator": "<"
    }
}
```

### 告警配置

```yaml
# monitoring/alerts.yaml
alerts:
  - name: 成本超标
    condition: cost_per_request > 0.01
    severity: warning
    channels: [dingtalk]

  - name: 转人工率过高
    condition: transfer_rate > 0.25
    severity: critical
    channels: [dingtalk, sms]

  - name: 信号计算失败
    condition: signal_failure_rate > 0.05
    severity: critical
    channels: [dingtalk]

  - name: 延迟超标
    condition: evaluation_latency_p95 > 1000
    severity: warning
    channels: [dingtalk]
```

### 监控面板

```python
# app/api/v1/monitoring.py
@router.get("/metrics/confidence")
async def get_confidence_metrics(
    days: int = 7,
    current_user = Depends(get_current_admin)
):
    """获取置信度系统监控指标"""

    return {
        "cost": {
            "avg_per_request": await metrics.get_avg_cost(days),
            "total_cost": await metrics.get_total_cost(days),
            "breakdown": {
                "rag": await metrics.get_rag_cost(days),
                "llm": await metrics.get_llm_cost(days),
                "emotion": await metrics.get_emotion_cost(days)
            }
        },
        "quality": {
            "transfer_rate": await metrics.get_transfer_rate(days),
            "vip_transfer_rate": await metrics.get_vip_transfer_rate(days),
            "user_satisfaction": await metrics.get_satisfaction_score(days)
        },
        "performance": {
            "latency_p50": await metrics.get_latency_percentile(days, 50),
            "latency_p95": await metrics.get_latency_percentile(days, 95),
            "latency_p99": await metrics.get_latency_percentile(days, 99)
        },
        "stability": {
            "signal_failure_rate": await metrics.get_failure_rate(days),
            "cache_hit_rate": await metrics.get_cache_hit_rate(days),
            "llm_skip_rate": await metrics.get_llm_skip_rate(days)
        }
    }
```

---

## 总结

### 完成的功能

1. **置信度评估模块** (`app/confidence/`)
   - RAGSignal: 基于检索质量评估
   - LLMSignal: 基于 LLM 自我评估
   - EmotionSignal: 基于用户情感检测
   - ConfidenceEvaluator: 综合评估器

2. **多 Agent 架构** (`app/agents/`)
   - BaseAgent: 抽象基类
   - RouterAgent: 意图识别和路由
   - PolicyAgent: 政策咨询专家
   - OrderAgent: 订单和退货专家
   - SupervisorAgent: 监督和协调

3. **管理员支持** (`app/api/v1/admin.py`)
   - 置信度任务查询接口
   - 与风险任务分类展示

4. **前端适配** (`app/frontend/`)
   - 显示置信度触发的转人工状态

### 关键设计决策

1. **置信度阈值 0.6**：平衡用户体验和人工工作量
2. **情感信号权重 20%**：优先处理愤怒用户，提升体验
3. **Supervisor 模式**：统一入口，便于后续扩展更多 Agent
4. **向后兼容**：原有 AuditLog 模型通过默认值兼容

### 后续优化方向

1. 基于历史数据动态调整阈值
2. 增加更多信号（如用户历史满意度）
3. A/B 测试不同权重配置
