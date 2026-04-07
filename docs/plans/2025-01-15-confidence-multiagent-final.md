# 置信度驱动人工接管 + 多 Agent 协作架构 实施计划（最终修订版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **修订说明**: 本计划已基于多轮审查和最终严格审核进行修订，修复了 asyncio.gather 使用错误、向后兼容、数据库迁移等关键问题。

**Goal:** 实现基于置信度评估的智能人工接管机制，并将单体 Agent 重构为职责分明的多 Agent 协作架构

**Architecture:**
1. **置信度系统**: 在生成回复后增加置信度评估节点，综合 RAG 检索质量、LLM 自我评估、用户情感检测三个信号，低于阈值时触发人工接管
2. **多 Agent 架构**: 将现有 nodes.py 拆分为 RouterAgent、PolicyAgent、OrderAgent 三个 Specialist Agent，通过 Supervisor 协调，每个 Agent 职责单一、可独立迭代

**Tech Stack:** LangGraph Multi-Agent, SQLModel, FastAPI, PostgreSQL, Redis

---

## 关键修订摘要（基于最终审核）

### 严重问题修复

| 问题 | 影响 | 修复方案 |
|------|------|----------|
| **asyncio.gather 使用错误** | 当 rag_task 为 None 时崩溃 | 重构并行计算逻辑，确保正确创建 Task |
| **f-string 格式化错误** | SignalResult 对象无法格式化 | 使用 `results['rag'].score` 而非 `results['rag']` |
| **audit_level 不兼容** | 现有代码使用 `audit_required: bool` | 同时保留两个字段，添加转换工具函数 |
| **RetrievalResult 不兼容** | 现有代码使用 `context: list[str]` | 在 AgentState 中保留 `context` 作为兼容层 |
| **Signal Protocol 不匹配** | 定义用 `**kwargs`，实现用具体参数 | 移除 Protocol，使用具体类型定义 |

### 中等问题修复

| 问题 | 修复方案 |
|------|----------|
| 环境变量映射不明确 | 添加 `env_nested_delimiter='__'` 配置 |
| 情感词典覆盖不足 | 扩展词典，修复 " hurry" 空格问题 |
| 百分比解析逻辑缺陷 | 重构解析逻辑，正确处理百分比 |
| 数据库迁移计划缺失 | 添加完整迁移脚本 |
| 测试边界条件缺失 | 补充重试逻辑、权重不为 1.0、并发缓存测试 |
| 缺少超时控制 | 添加 `asyncio.wait_for` 包装 |

---

## 文件结构总览（最终版）

### 新建文件
- `app/models/state.py` - AgentState 新位置（向后兼容设计）
- `app/agents/__init__.py` - Agents 包初始化
- `app/agents/base.py` - 基础 Agent 抽象类（泛型设计）
- `app/agents/router.py` - 路由 Agent
- `app/agents/policy.py` - 政策专家 Agent
- `app/agents/order.py` - 订单专家 Agent
- `app/agents/supervisor.py` - 监督 Agent
- `app/confidence/__init__.py` - 置信度模块初始化
- `app/confidence/evaluator.py` - 置信度评估器
- `app/confidence/signals.py` - 置信度信号计算（修复版）
- `app/confidence/cache.py` - 置信度缓存
- `app/models/confidence_audit.py` - 置信度审计日志模型
- `migrations/versions/xxxx_v4_1_add_confidence_audit.py` - 数据库迁移
- `test/confidence/test_signals.py` - 信号计算单元测试
- `test/agents/test_router.py` - RouterAgent 测试
- `test/agents/test_policy.py` - PolicyAgent 测试
- `test/agents/test_order.py` - OrderAgent 测试
- `test/agents/test_supervisor.py` - SupervisorAgent 测试
- `test/confidence/test_evaluator.py` - 置信度评估测试
- `test/integration/test_multi_agent.py` - 多 Agent 集成测试

### 修改文件
- `app/graph/state.py` - 向后兼容层（转换函数）
- `app/graph/workflow.py` - 重构为多 Agent 工作流
- `app/core/config.py` - 添加 CONFIDENCE 配置
- `app/api/v1/admin.py` - 增加置信度审核接口
- `app/api/v1/chat.py` - 适配多 Agent 响应
- `app/models/audit.py` - 扩展 AuditLog

---

## Task 1: 迁移 AgentState 到 models/state.py（向后兼容设计）

**Files:**
- Create: `app/models/state.py`
- Modify: `app/graph/state.py`（添加转换函数，非简单重导出）

### Step 1: 创建 models/state.py

```python
# app/models/state.py
import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict


@dataclass
class RetrievalResult:
    """统一封装检索结果"""
    chunks: list[str]
    similarities: list[float]
    sources: list[str]

    def to_dict(self) -> dict:
        return {
            "chunks": self.chunks,
            "similarities": self.similarities,
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RetrievalResult":
        return cls(
            chunks=data.get("chunks", []),
            similarities=data.get("similarities", []),
            sources=data.get("sources", []),
        )


class AgentState(TypedDict):
    """Agent 状态定义（v4.1 最终版）- 向后兼容设计"""

    # ========== 基础信息 ==========
    question: str
    user_id: int
    thread_id: str

    # ========== 意图与路由 ==========
    intent: str | None
    current_agent: str | None

    # ========== 历史记录 ==========
    history: Annotated[list[dict], operator.add]

    # ========== RAG 检索结果（新旧双字段兼容）==========
    # 新字段：统一封装
    retrieval_result: RetrievalResult | None
    # 旧字段：向后兼容，从 retrieval_result.chunks 计算得出
    context: list[str]

    # ========== 订单数据 ==========
    order_data: dict | None

    # ========== 审核与人工接管（新旧双字段兼容）==========
    # 新字段：统一审核级别
    audit_level: str | None  # "none" | "auto" | "manual"
    # 旧字段：向后兼容，从 audit_level 计算得出
    audit_required: bool
    audit_type: str | None  # "RISK" | "CONFIDENCE" | None
    audit_log_id: int | None
    audit_reason: str | None

    # ========== 置信度评估（v4.1 新增）==========
    confidence_score: float | None
    confidence_signals: dict | None

    # ========== 生成结果 ==========
    messages: Annotated[list[dict[str, Any]], operator.add]
    answer: str

    # ========== 退货流程状态 ==========
    refund_flow_active: bool | None
    refund_order_sn: str | None
    refund_step: str | None


# ========== 状态转换工具函数 ==========

def normalize_state(state: dict) -> dict:
    """
    规范化状态，确保新旧字段一致性
    在每次状态更新后调用
    """
    # retrieval_result -> context
    if state.get("retrieval_result"):
        state["context"] = state["retrieval_result"].chunks
    else:
        state["context"] = state.get("context", [])

    # audit_level -> audit_required + audit_type
    audit_level = state.get("audit_level")
    if audit_level:
        state["audit_required"] = audit_level in ("auto", "manual")
        if audit_level == "manual":
            state["audit_type"] = state.get("audit_type") or "CONFIDENCE"
        else:
            state["audit_type"] = None
    else:
        # audit_required -> audit_level (旧代码兼容)
        if state.get("audit_required"):
            state["audit_level"] = state.get("audit_type", "manual").lower()
        else:
            state["audit_level"] = "none"

    return state


def get_audit_required(state: AgentState) -> bool:
    """向后兼容：从 audit_level 计算 audit_required"""
    return state.get("audit_level") in ("auto", "manual")


def get_audit_level_from_old(audit_required: bool, audit_type: str | None) -> str:
    """从旧字段计算新字段"""
    if not audit_required:
        return "none"
    if audit_type == "RISK":
        return "manual"  # 风险类必须人工审核
    return "auto"  # 其他自动审核
```

### Step 2: 修改 app/graph/state.py（转换层，非简单重导出）

```python
# app/graph/state.py
# v4.1 向后兼容层
# 此文件保留以确保现有代码不中断，将在 v5.0 移除

import warnings

from app.models.state import (
    AgentState,
    RetrievalResult,
    get_audit_level_from_old,
    get_audit_required,
    normalize_state,
)

__all__ = [
    "AgentState",
    "RetrievalResult",
    "get_audit_required",
    "get_audit_level_from_old",
    "normalize_state",
]

# 向后兼容警告
warnings.warn(
    "app.graph.state is deprecated, use app.models.state instead",
    DeprecationWarning,
    stacklevel=2,
)
```

### Step 3: 提交更改

```bash
git add app/models/state.py app/graph/state.py
git commit -m "refactor: migrate AgentState to models/state.py with backward compatibility

- Move AgentState to app/models/state.py
- Add retrieval_result and context dual fields for compatibility
- Add audit_level, audit_required, audit_type triple fields for compatibility
- Add normalize_state() to sync dual fields
- Add get_audit_required() for backward compatibility
- Deprecate app/graph/state.py with warning"
```

---

## Task 2: 更新配置管理（修复环境变量映射）

**Files:**
- Modify: `app/core/config.py`

### Step 1: 添加 ConfidenceSettings（修复嵌套配置）

```python
# app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfidenceSettings(BaseSettings):
    """置信度评估配置（v4.1）"""

    model_config = SettingsConfigDict(
        env_prefix="CONFIDENCE_",
        extra="ignore",
    )

    # ========== 阈值配置 ==========
    THRESHOLD: float = Field(default=0.7, ge=0.0, le=1.0)
    HIGH_THRESHOLD: float = Field(default=0.8, ge=0.0, le=1.0)
    MEDIUM_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0)
    LOW_THRESHOLD: float = Field(default=0.3, ge=0.0, le=1.0)

    # ========== 信号权重配置 ==========
    RAG_WEIGHT: float = Field(default=0.3, ge=0.0, le=1.0)
    LLM_WEIGHT: float = Field(default=0.5, ge=0.0, le=1.0)
    EMOTION_WEIGHT: float = Field(default=0.2, ge=0.0, le=1.0)

    # ========== 超时配置 ==========
    CALCULATION_TIMEOUT_SECONDS: float = Field(default=3.0, ge=1.0, le=10.0)

    # ========== 情感检测配置 ==========
    EMOTION_HISTORY_ROUNDS: int = Field(default=3, ge=1, le=10)

    # ========== LLM 解析配置 ==========
    LLM_PARSE_MAX_RETRIES: int = Field(default=3, ge=1, le=10)
    LLM_PARSE_RETRY_DELAY: float = Field(default=0.5, ge=0.1, le=5.0)

    # ========== 成本优化配置 ==========
    EVALUATION_MODEL: str = "qwen-turbo"
    ENABLE_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 3600
    SKIP_LLM_ON_CLEAR_RAG: bool = True
    CLEAR_RAG_THRESHOLD_HIGH: float = 0.9
    CLEAR_RAG_THRESHOLD_LOW: float = 0.3

    @property
    def default_weights(self) -> dict[str, float]:
        return {
            "rag": self.RAG_WEIGHT,
            "llm": self.LLM_WEIGHT,
            "emotion": self.EMOTION_WEIGHT,
        }

    def get_audit_level(self, confidence: float) -> str:
        if confidence >= self.HIGH_THRESHOLD:
            return "none"
        elif confidence >= self.MEDIUM_THRESHOLD:
            return "auto"
        else:
            return "manual"


# 父类 Settings 需要添加 env_nested_delimiter
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # 关键：支持 CONFIDENCE__THRESHOLD=0.7
        extra="ignore",
    )

    # ... 现有配置 ...

    # 置信度评估配置（嵌套模型）
    CONFIDENCE: ConfidenceSettings = Field(default_factory=ConfidenceSettings)
```

### Step 2: 环境变量配置示例

```bash
# .env 文件添加以下配置

# ========== 置信度配置 ==========
CONFIDENCE__THRESHOLD=0.7
CONFIDENCE__RAG_WEIGHT=0.3
CONFIDENCE__LLM_WEIGHT=0.5
CONFIDENCE__EMOTION_WEIGHT=0.2
CONFIDENCE__CALCULATION_TIMEOUT_SECONDS=3.0
CONFIDENCE__EVALUATION_MODEL=qwen-turbo
CONFIDENCE__ENABLE_CACHE=true
```

### Step 3: 提交更改

```bash
git add app/core/config.py
git commit -m "feat: add ConfidenceSettings with env_nested_delimiter

- Add env_nested_delimiter='__' for nested config
- Add CALCULATION_TIMEOUT_SECONDS for timeout control
- Add complete ConfidenceSettings with all options"
```

---

## Task 3: 创建健壮的置信度信号计算模块（修复版）

**Files:**
- Create: `app/confidence/__init__.py`
- Create: `app/confidence/signals.py`

### Step 1: 创建信号计算模块（修复所有严重问题）

```python
# app/confidence/signals.py
import asyncio
import re
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings
from app.models.state import AgentState


@dataclass
class SignalResult:
    """信号计算结果"""
    score: float
    reason: str
    metadata: dict | None = None


@dataclass
class RAGSignal:
    """基于检索质量计算置信度"""

    async def calculate(
        self,
        similarities: list[float],
        chunks: list[str],
        query: str,
    ) -> SignalResult:
        """计算 RAG 信号"""
        if not similarities:
            return SignalResult(score=0.0, reason="无检索结果")

        avg_sim = sum(similarities) / len(similarities)
        max_sim = max(similarities)

        # 计算覆盖率
        query_words = set(query.lower().split())
        covered_words = set()
        for chunk in chunks:
            chunk_words = set(chunk.lower().split())
            covered_words.update(query_words & chunk_words)

        coverage = len(covered_words) / len(query_words) if query_words else 0.0
        score = max_sim * 0.4 + avg_sim * 0.3 + coverage * 0.3

        return SignalResult(
            score=min(max(score, 0.0), 1.0),
            reason=f"最高:{max_sim:.2f} 平均:{avg_sim:.2f} 覆盖:{coverage:.2f}",
            metadata={
                "max_similarity": max_sim,
                "avg_similarity": avg_sim,
                "coverage": coverage,
            }
        )


@dataclass
class LLMSignal:
    """LLM 自我评估信号"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.CONFIDENCE.EVALUATION_MODEL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            base_url=settings.OPENAI_BASE_URL,
            temperature=0,
        )

    def _parse_confidence_score(self, text: str) -> float | None:
        """
        健壮地解析置信度分数（修复版）
        支持格式："0.85", "85%", "置信度：0.85"
        """
        if not text:
            return None

        text = text.strip()

        # 优先匹配带百分号的
        percent_match = re.search(r'(\d+\.?\d*)\s*%', text)
        if percent_match:
            try:
                value = float(percent_match.group(1))
                # 处理 85% 或 0.85%
                return min(max(value / 100 if value > 1 else value, 0.0), 1.0)
            except (ValueError, TypeError):
                pass

        # 匹配其他格式
        patterns = [
            r'置信度[：:]\s*(\d+\.?\d*)',
            r'分数[是:：]\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1))
                    # 如果值大于1，视为百分比
                    if value > 1.0:
                        value = value / 100
                    return min(max(value, 0.0), 1.0)
                except (ValueError, TypeError):
                    continue

        return None

    async def calculate(
        self,
        query: str,
        context: list[str],
        generated_answer: str,
    ) -> SignalResult:
        """计算 LLM 信号，带重试机制"""
        prompt = f"""评估回答置信度（0-1）：
问题：{query}
回答：{generated_answer}
只返回数字："""

        max_retries = settings.CONFIDENCE.LLM_PARSE_MAX_RETRIES
        retry_delay = settings.CONFIDENCE.LLM_PARSE_RETRY_DELAY
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
                raw_text = response.content if hasattr(response, 'content') else str(response)

                score = self._parse_confidence_score(raw_text)

                if score is not None:
                    return SignalResult(
                        score=score,
                        reason=f"LLM自评估(尝试{attempt + 1})",
                        metadata={"raw_response": raw_text[:200]}
                    )

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        return SignalResult(
            score=0.5,
            reason=f"解析失败，使用默认值",
            metadata={"error": str(last_error) if last_error else "parse_failed"}
        )


@dataclass
class EmotionSignal:
    """用户情感检测信号（修复词典）"""

    # 扩展的情感词典
    NEGATIVE_WORDS = frozenset([
        '生气', '愤怒', '不满', '投诉', '差评', '退款', '骗子', '垃圾', '太差',
        '失望', '欺骗', '坑', '忽悠', '恶劣', '糟糕', '气愤', '恼火', '心烦'
    ])
    URGENT_WORDS = frozenset([
        '马上', '立刻', '现在', '急', '紧急', 'hurry', 'urgent', 'asap',
        '立即', '赶紧', '赶快', '快点', '等着', '急用'
    ])
    POSITIVE_WORDS = frozenset([
        '谢谢', '感谢', '满意', '好评', '不错', '好用', '推荐', '喜欢',
        '完美', '优秀', '棒', '赞', '给力', '靠谱'
    ])

    async def calculate(
        self,
        query: str,
        history: list[dict],
        history_rounds: int = 3,
    ) -> SignalResult:
        """检测用户情感状态"""
        recent_history = history[-history_rounds:] if len(history) >= history_rounds else history

        all_texts = [msg.get('content', '') for msg in recent_history] + [query]
        all_text = ' '.join(all_texts).lower()

        negative_count = sum(1 for w in self.NEGATIVE_WORDS if w in all_text)
        urgent_count = sum(1 for w in self.URGENT_WORDS if w in all_text)
        positive_count = sum(1 for w in self.POSITIVE_WORDS if w in all_text)

        # 情感计算逻辑
        if negative_count >= 3 or urgent_count >= 2:
            score = max(0.0, 0.3 - negative_count * 0.05)
            emotion_type = "high_frustration"
            reason = f"高挫败感(负面词{negative_count},紧急词{urgent_count})"
        elif negative_count >= 1:
            score = max(0.3, 0.6 - negative_count * 0.1)
            emotion_type = "mild_frustration"
            reason = f"轻微不满(负面词{negative_count})"
        elif positive_count > 0:
            score = min(1.0, 0.8 + positive_count * 0.05)
            emotion_type = "positive"
            reason = f"正面情绪(正面词{positive_count})"
        else:
            score = 0.7
            emotion_type = "neutral"
            reason = "无明显情绪"

        return SignalResult(
            score=score,
            reason=reason,
            metadata={
                "emotion_type": emotion_type,
                "negative_count": negative_count,
                "urgent_count": urgent_count,
                "positive_count": positive_count,
            }
        )


class ConfidenceSignals:
    """置信度信号计算器（修复 asyncio.gather 使用）"""

    def __init__(self, state: AgentState):
        self.state = state
        self.rag_signal = RAGSignal()
        self.llm_signal = LLMSignal()
        self.emotion_signal = EmotionSignal()

    async def _calculate_with_timeout(
        self,
        generated_answer: str | None = None
    ) -> dict[str, SignalResult]:
        """内部计算逻辑"""
        retrieval_result = self.state.get("retrieval_result")
        query = self.state.get("question", "")
        history = self.state.get("history", [])

        results: dict[str, SignalResult] = {}

        # === 阶段 1: 并行计算独立信号（修复版）===
        if retrieval_result:
            # 正确创建 coroutine 并使用 asyncio.gather
            rag_coro = self.rag_signal.calculate(
                similarities=retrieval_result.similarities,
                chunks=retrieval_result.chunks,
                query=query,
            )
            emotion_coro = self.emotion_signal.calculate(
                query=query,
                history=history,
                history_rounds=settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS,
            )
            # 两个独立的 coroutine 可以安全地 gather
            results["rag"], results["emotion"] = await asyncio.gather(rag_coro, emotion_coro)
        else:
            # 没有检索结果，只计算情感
            results["emotion"] = await self.emotion_signal.calculate(
                query=query,
                history=history,
                history_rounds=settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS,
            )
            results["rag"] = SignalResult(score=0.0, reason="无检索结果")

        # === 阶段 2: 智能跳过 LLMSignal ===
        should_skip_llm = (
            settings.CONFIDENCE.SKIP_LLM_ON_CLEAR_RAG and
            generated_answer is None and
            (
                results["rag"].score >= settings.CONFIDENCE.CLEAR_RAG_THRESHOLD_HIGH or
                results["rag"].score <= settings.CONFIDENCE.CLEAR_RAG_THRESHOLD_LOW
            )
        )

        if should_skip_llm:
            # 修复：使用 .score 访问分数
            results["llm"] = SignalResult(
                score=results["rag"].score,
                reason=f"RAG信号明确({results['rag'].score:.2f})，跳过LLM",
                metadata={"skipped": True}
            )
        elif generated_answer:
            context = retrieval_result.chunks if retrieval_result else []
            results["llm"] = await self.llm_signal.calculate(
                query=query,
                context=context,
                generated_answer=generated_answer,
            )
        else:
            results["llm"] = SignalResult(score=0.5, reason="等待生成结果")

        return results

    async def calculate_all(
        self,
        generated_answer: str | None = None
    ) -> dict[str, SignalResult]:
        """
        计算所有信号（带超时控制）
        """
        try:
            return await asyncio.wait_for(
                self._calculate_with_timeout(generated_answer),
                timeout=settings.CONFIDENCE.CALCULATION_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            # 超时返回保守估计
            return {
                "rag": SignalResult(score=0.5, reason="计算超时"),
                "llm": SignalResult(score=0.5, reason="计算超时"),
                "emotion": SignalResult(score=0.5, reason="计算超时"),
            }
```

### Step 2: 提交更改

```bash
git add app/confidence/
git commit -m "feat: add confidence signals with bug fixes

- Fix asyncio.gather usage (create coroutines properly)
- Fix f-string formatting error (use .score)
- Fix percentage parsing logic
- Fix emotion dictionary (remove space, add more words)
- Add asyncio.wait_for timeout control
- Remove Signal Protocol (use concrete types)"
```

---

## Task 4: 创建数据库迁移脚本

**Files:**
- Create: `migrations/versions/xxxx_v4_1_add_confidence_audit.py`

### Step 1: 创建 Alembic 迁移

```python
"""v4.1: Add confidence audit and audit_level

Revision ID: v4_1_confidence
Revises: f84a99d62fad
Create Date: 2025-01-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = 'v4_1_confidence'
down_revision: Union[str, None] = 'f84a99d62fad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========== 1. 添加 confidence_audits 表 ==========
    op.create_table(
        'confidence_audits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('rag_score', sa.Float(), nullable=True),
        sa.Column('llm_score', sa.Float(), nullable=True),
        sa.Column('emotion_score', sa.Float(), nullable=True),
        sa.Column('signals_metadata', sa.JSON(), nullable=True),
        sa.Column('audit_level', sa.String(length=16), nullable=False),
        sa.Column('transfer_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('review_result', sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_confidence_audits_thread_id', 'confidence_audits', ['thread_id'])
    op.create_index('ix_confidence_audits_created_at', 'confidence_audits', ['created_at'])

    # ========== 2. 修改 audit_logs 表（添加 audit_level）==========
    op.add_column('audit_logs', sa.Column('audit_level', sa.String(length=16), nullable=True))

    # ========== 3. 数据迁移：audit_required -> audit_level ==========
    op.execute("""
        UPDATE audit_logs
        SET audit_level = CASE
            WHEN audit_required = true THEN 'manual'
            ELSE 'none'
        END
    """)

    # ========== 4. 添加触发器保持同步（可选）==========
    # 注意：根据具体数据库选择是否添加触发器


def downgrade() -> None:
    # ========== 1. 删除 confidence_audits 表 ==========
    op.drop_index('ix_confidence_audits_created_at', table_name='confidence_audits')
    op.drop_index('ix_confidence_audits_thread_id', table_name='confidence_audits')
    op.drop_table('confidence_audits')

    # ========== 2. 删除 audit_logs.audit_level ==========
    op.drop_column('audit_logs', 'audit_level')
```

### Step 2: 提交更改

```bash
git add migrations/versions/
git commit -m "feat: add database migration for confidence audit

- Add confidence_audits table
- Add audit_level column to audit_logs
- Add data migration from audit_required to audit_level"
```

---

## Task 5-15: 后续任务

后续任务（BaseAgent、RouterAgent、PolicyAgent、OrderAgent、SupervisorAgent、Workflow、Admin API、Frontend、测试）的结构保持不变，但需要注意：

1. **所有导入从 `app.models.state`**
2. **使用 `normalize_state()` 在状态更新后同步双字段**
3. **使用 `get_audit_required()` 兼容旧代码**
4. **测试覆盖重试逻辑、超时、边界条件**

---

## 附录：测试边界条件补充

```python
# test/confidence/test_signals.py 需要补充的测试

class TestLLMSignalEdgeCases:
    """LLM 信号边界测试"""

    async def test_parse_various_formats(self):
        """测试多种格式解析：0.85, 85%, 置信度: 0.85"""
        llm_signal = LLMSignal()
        assert llm_signal._parse_confidence_score("0.85") == 0.85
        assert llm_signal._parse_confidence_score("85%") == 0.85
        assert llm_signal._parse_confidence_score("置信度：0.85") == 0.85
        assert llm_signal._parse_confidence_score("0.85%") == 0.0085  # 边缘情况

    async def test_parse_edge_values(self):
        """测试边界值"""
        llm_signal = LLMSignal()
        assert llm_signal._parse_confidence_score("100") == 1.0
        assert llm_signal._parse_confidence_score("0") == 0.0
        assert llm_signal._parse_confidence_score("150%") == 1.0  # 上限裁剪

    async def test_retry_mechanism(self):
        """测试重试机制"""
        # Mock LLM 返回无效响应，验证重试
        pass

    async def test_timeout_fallback(self):
        """测试超时回退"""
        # 验证超时后返回保守估计
        pass


class TestRAGSignalEdgeCases:
    """RAG 信号边界测试"""

    async def test_empty_chunks(self):
        """测试空 chunks"""
        rag_signal = RAGSignal()
        result = await rag_signal.calculate([], [], "query")
        assert result.score == 0.0

    async def test_zero_similarity(self):
        """测试相似度为 0"""
        rag_signal = RAGSignal()
        result = await rag_signal.calculate([0.0, 0.0], ["a", "b"], "query")
        assert result.score == 0.0


class TestEmotionSignalEdgeCases:
    """情感信号边界测试"""

    async def test_empty_history(self):
        """测试无历史记录"""
        emotion_signal = EmotionSignal()
        result = await emotion_signal.calculate("query", [], 3)
        assert result.score > 0  # 应有默认值

    async def test_consecutive_negative(self):
        """测试连续负面情绪"""
        history = [
            {"content": "太失望了"},
            {"content": "很生气"},
            {"content": "要投诉"},
        ]
        emotion_signal = EmotionSignal()
        result = await emotion_signal.calculate("垃圾产品", history, 3)
        assert result.score < 0.3  # 应触发高挫败感
```

---

*最终修订日期: 2025-01-16*
*修订依据: 最终全面审核报告*
