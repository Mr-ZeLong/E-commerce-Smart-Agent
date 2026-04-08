# 意图识别系统重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有的规则+LLM混合意图识别重构为分层意图体系（Function Calling + Few-shot），实现智能澄清机制、槽位管理和话题切换检测。

**Architecture:** 采用分层架构：IntentClassifier（Function Calling分类器）→ SlotValidator（槽位验证）→ ClarificationEngine（澄清引擎）→ TopicSwitchDetector（话题切换检测）。新系统替换现有的RouterAgent，与SupervisorAgent集成。

**Tech Stack:** Python 3.12, LangChain, OpenAI Function Calling, Pydantic, Pytest

---

## 文件结构概览

### 新增文件（12个）

| 文件路径 | 职责 |
|---------|------|
| `app/intent/models.py` | 数据模型：IntentResult, ClarificationState, Slot等 |
| `app/intent/config.py` | 配置：意图定义、槽位优先级、三级意图约束 |
| `app/intent/classifier.py` | 意图分类器：Function Calling实现 |
| `app/intent/slot_validator.py` | 槽位验证器：检查完整性、优先级管理 |
| `app/intent/clarification.py` | 澄清引擎：生成追问问题、处理用户拒绝 |
| `app/intent/topic_switch.py` | 话题切换检测器：显式/隐式切换检测 |
| `app/intent/multi_intent.py` | 多意图处理器：拆分、槽位共享、优先级排序 |
| `app/intent/safety.py` | 安全过滤：关键词、Prompt注入、语义检测 |
| `app/intent/service.py` | 服务层：整合所有组件的对外接口 |
| `app/intent/__init__.py` | 包导出 |
| `tests/intent/test_classifier.py` | 意图分类器测试 |
| `tests/intent/test_clarification.py` | 澄清机制测试 |
| `tests/intent/test_integration.py` | 集成测试 |

### 修改文件（2个）

| 文件路径 | 修改内容 |
|---------|---------|
| `app/agents/router.py` | 替换为新的IntentRouterAgent，使用新意图系统 |
| `app/agents/__init__.py` | 导出新的RouterAgent |

---

## Task 1: 创建意图识别模块基础结构

**Files:**
- Create: `app/intent/__init__.py`
- Create: `app/intent/models.py`
- Test: `tests/intent/__init__.py`

### 步骤1: 创建intent包

- [ ] **Step 1: 创建app/intent目录和__init__.py**

```bash
mkdir -p app/intent tests/intent
```

创建 `app/intent/__init__.py`:

```python
"""意图识别模块

提供分层意图识别、槽位管理、澄清机制等功能。
"""

from app.intent.models import (
    IntentResult,
    ClarificationState,
    Slot,
    SlotPriority,
    IntentCategory,
)
from app.intent.service import IntentRecognitionService

__all__ = [
    "IntentResult",
    "ClarificationState",
    "Slot",
    "SlotPriority",
    "IntentCategory",
    "IntentRecognitionService",
]
```

- [ ] **Step 2: 创建基础数据模型**

创建 `app/intent/models.py`:

```python
"""意图识别数据模型"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntentCategory(str, Enum):
    """一级意图：业务域"""
    ORDER = "ORDER"
    AFTER_SALES = "AFTER_SALES"
    POLICY = "POLICY"
    ACCOUNT = "ACCOUNT"
    PROMOTION = "PROMOTION"
    PAYMENT = "PAYMENT"
    LOGISTICS = "LOGISTICS"
    PRODUCT = "PRODUCT"
    RECOMMENDATION = "RECOMMENDATION"
    CART = "CART"
    COMPLAINT = "COMPLAINT"
    OTHER = "OTHER"


class IntentAction(str, Enum):
    """二级意图：动作类型"""
    QUERY = "QUERY"
    APPLY = "APPLY"
    MODIFY = "MODIFY"
    CANCEL = "CANCEL"
    CONSULT = "CONSULT"
    ADD = "ADD"
    REMOVE = "REMOVE"
    COMPARE = "COMPARE"


class SlotPriority(str, Enum):
    """槽位优先级"""
    P0 = "P0"  # 必须
    P1 = "P1"  # 重要
    P2 = "P2"  # 可选


@dataclass
class Slot:
    """槽位定义"""
    name: str
    description: str
    priority: SlotPriority
    required: bool = True
    extractor: str | None = None  # 提取器名称，如"order_sn_extractor"


@dataclass
class IntentResult:
    """意图识别结果"""
    primary_intent: IntentCategory
    secondary_intent: IntentAction
    tertiary_intent: str | None = None
    confidence: float = 0.0
    slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None
    raw_query: str = ""

    def to_dict(self) -> dict:
        return {
            "primary_intent": self.primary_intent.value,
            "secondary_intent": self.secondary_intent.value,
            "tertiary_intent": self.tertiary_intent,
            "confidence": self.confidence,
            "slots": self.slots,
            "missing_slots": self.missing_slots,
            "needs_clarification": self.needs_clarification,
        }


@dataclass
class ClarificationState:
    """澄清状态"""
    session_id: str
    current_intent: IntentResult | None = None
    clarification_round: int = 0
    max_clarification_rounds: int = 3
    asked_slots: list[str] = field(default_factory=list)
    collected_slots: dict[str, Any] = field(default_factory=dict)
    pending_slot: str | None = None
    user_refused_slots: list[str] = field(default_factory=list)
    clarification_history: list[dict] = field(default_factory=list)

    def can_continue_clarification(self) -> bool:
        return self.clarification_round < self.max_clarification_rounds

    def increment_round(self):
        self.clarification_round += 1
```

- [ ] **Step 3: 创建测试目录**

创建 `tests/intent/__init__.py`:

```python
"""意图识别模块测试"""
```

- [ ] **Step 4: 运行模型基础测试**

创建 `tests/intent/test_models.py`:

```python
"""测试数据模型"""

import pytest
from app.intent.models import (
    IntentCategory,
    IntentAction,
    SlotPriority,
    Slot,
    IntentResult,
    ClarificationState,
)


def test_intent_category_values():
    assert IntentCategory.ORDER.value == "ORDER"
    assert IntentCategory.AFTER_SALES.value == "AFTER_SALES"
    assert IntentCategory.OTHER.value == "OTHER"


def test_intent_action_values():
    assert IntentAction.QUERY.value == "QUERY"
    assert IntentAction.APPLY.value == "APPLY"


def test_slot_priority_values():
    assert SlotPriority.P0.value == "P0"
    assert SlotPriority.P1.value == "P1"
    assert SlotPriority.P2.value == "P2"


def test_slot_creation():
    slot = Slot(
        name="order_sn",
        description="订单号",
        priority=SlotPriority.P0,
        required=True,
    )
    assert slot.name == "order_sn"
    assert slot.priority == SlotPriority.P0


def test_intent_result_defaults():
    result = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.QUERY,
    )
    assert result.confidence == 0.0
    assert result.slots == {}
    assert result.needs_clarification is False


def test_intent_result_to_dict():
    result = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.QUERY,
        confidence=0.95,
        slots={"order_sn": "SN001"},
    )
    data = result.to_dict()
    assert data["primary_intent"] == "ORDER"
    assert data["confidence"] == 0.95


def test_clarification_state_can_continue():
    state = ClarificationState(session_id="test_123")
    assert state.can_continue_clarification() is True

    state.clarification_round = 3
    assert state.can_continue_clarification() is False


def test_clarification_state_increment():
    state = ClarificationState(session_id="test_123")
    state.increment_round()
    assert state.clarification_round == 1
```

运行测试：

```bash
cd /home/zelon/projects/E-commerce-Smart-Agent
python -m pytest tests/intent/test_models.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add app/intent/ tests/intent/
git commit -m "feat(intent): 添加意图识别模块基础数据模型

- 定义IntentCategory一级意图枚举
- 定义IntentAction二级意图枚举
- 定义SlotPriority槽位优先级
- 实现IntentResult和ClarificationState数据类
- 添加基础单元测试

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 实现意图配置系统

**Files:**
- Create: `app/intent/config.py`
- Test: `tests/intent/test_config.py`

### 步骤1: 创建配置模块

- [ ] **Step 1: 编写意图配置**

创建 `app/intent/config.py`:

```python
"""意图识别配置

定义意图层级、槽位优先级、三级意图约束等配置。
"""

from app.intent.models import IntentCategory, IntentAction, SlotPriority, Slot


# ============== 意图兼容性矩阵 ==============
# 定义哪些意图之间可以平滑切换（同域或关联意图）
INTENT_COMPATIBILITY: dict[str, list[str]] = {
    # AFTER_SALES域内兼容
    "AFTER_SALES/APPLY": [
        "AFTER_SALES/CONSULT",
        "AFTER_SALES/CANCEL",
        "AFTER_SALES/MODIFY",
    ],
    "AFTER_SALES/CONSULT": [
        "AFTER_SALES/APPLY",
        "POLICY/CONSULT",
    ],
    # ORDER与LOGISTICS关联
    "ORDER/QUERY": ["LOGISTICS/QUERY", "AFTER_SALES/APPLY"],
    "LOGISTICS/QUERY": ["ORDER/QUERY", "ORDER/MODIFY"],
    # PRODUCT与RECOMMENDATION关联
    "PRODUCT/QUERY": ["RECOMMENDATION/CONSULT", "PRODUCT/COMPARE"],
    "RECOMMENDATION/CONSULT": ["PRODUCT/QUERY", "PRODUCT/COMPARE"],
    # CART与ORDER关联
    "CART/QUERY": ["ORDER/APPLY", "CART/MODIFY"],
    "CART/ADD": ["CART/QUERY", "ORDER/APPLY"],
}


# ============== 三级意图配置 ==============
# 定义每个(primary, secondary)组合允许的三级意图
TERTIARY_INTENT_CONFIG: dict[tuple[str, str], dict] = {
    # AFTER_SALES场景
    ("AFTER_SALES", "APPLY"): {
        "tertiary_intents": ["REFUND", "EXCHANGE", "REPAIR"],
        "description": "申请售后",
    },
    ("AFTER_SALES", "CONSULT"): {
        "tertiary_intents": [
            "REFUND_SHIPPING_FEE",
            "REFUND_TIMELINE",
            "EXCHANGE_SIZE",
            "WARRANTY_POLICY",
        ],
        "description": "售后政策咨询",
    },
    # ORDER场景
    ("ORDER", "QUERY"): {
        "tertiary_intents": [
            "ORDER_TRACKING_DETAIL",
            "ORDER_STATUS_ESTIMATE",
            "ORDER_AMOUNT_DETAIL",
        ],
        "description": "订单查询",
    },
    # POLICY场景
    ("POLICY", "CONSULT"): {
        "tertiary_intents": [
            "POLICY_RETURN_EXCEPTION",
            "POLICY_SHIPPING_FEE",
            "POLICY_DELIVERY_TIME",
        ],
        "description": "政策咨询",
    },
    # PRODUCT场景
    ("PRODUCT", "QUERY"): {
        "tertiary_intents": [
            "PRODUCT_STOCK",
            "PRODUCT_SPEC",
            "PRODUCT_DETAIL",
            "PRODUCT_PRICE_COMPARE",
            "PRODUCT_REVIEW",
        ],
        "description": "商品查询",
    },
    ("PRODUCT", "COMPARE"): {
        "tertiary_intents": ["PRODUCT_PRICE_COMPARE", "PRODUCT_SPEC_COMPARE"],
        "description": "商品比较",
    },
    # RECOMMENDATION场景
    ("RECOMMENDATION", "CONSULT"): {
        "tertiary_intents": [
            "RECOMMEND_SIMILAR",
            "RECOMMEND_COMPLEMENTARY",
            "RECOMMEND_PERSONALIZED",
            "RECOMMEND_TRENDING",
        ],
        "description": "商品推荐",
    },
    # CART场景
    ("CART", "QUERY"): {
        "tertiary_intents": ["CART_VIEW", "CART_CHECKOUT"],
        "description": "购物车查询",
    },
    ("CART", "ADD"): {
        "tertiary_intents": ["CART_ADD_ITEM", "CART_ADD_BULK"],
        "description": "添加购物车",
    },
    ("CART", "REMOVE"): {
        "tertiary_intents": ["CART_REMOVE_ITEM", "CART_CLEAR_ALL"],
        "description": "移除购物车商品",
    },
}


def validate_tertiary_intent(
    primary: IntentCategory,
    secondary: IntentAction,
    tertiary: str | None,
) -> bool:
    """验证三级意图是否合法"""
    if tertiary is None:
        return True

    key = (primary.value, secondary.value)
    if key not in TERTIARY_INTENT_CONFIG:
        return False

    allowed = TERTIARY_INTENT_CONFIG[key]["tertiary_intents"]
    return tertiary in allowed


# ============== 槽位优先级配置 ==============
SLOT_PRIORITY_CONFIG: dict[str, dict[str, dict[str, list[str]]]] = {
    "AFTER_SALES": {
        "APPLY": {
            "P0": ["order_sn", "action_type"],
            "P1": ["reason_category", "specific_item"],
            "P2": ["reason_detail", "preferred_contact"],
        },
        "CONSULT": {
            "P0": ["policy_topic"],
            "P1": ["specific_item", "order_sn"],
            "P2": [],
        },
    },
    "ORDER": {
        "QUERY": {
            "P0": ["order_sn"],  # 可为"最近订单"
            "P1": ["query_type"],
            "P2": ["phone"],
        },
        "MODIFY": {
            "P0": ["order_sn", "modify_field"],
            "P1": ["new_value"],
            "P2": [],
        },
    },
    "PRODUCT": {
        "QUERY": {
            "P0": ["product_name"],
            "P1": ["product_id", "specification"],
            "P2": ["price_range"],
        },
        "COMPARE": {
            "P0": ["product_names"],
            "P1": ["compare_aspect"],
            "P2": [],
        },
    },
    "CART": {
        "QUERY": {
            "P0": [],
            "P1": [],
            "P2": [],
        },
        "ADD": {
            "P0": ["product_name"],
            "P1": ["quantity", "specification"],
            "P2": [],
        },
        "REMOVE": {
            "P0": ["product_name"],
            "P1": [],
            "P2": [],
        },
    },
    "POLICY": {
        "CONSULT": {
            "P0": ["policy_topic"],
            "P1": ["specific_item"],
            "P2": [],
        },
    },
}


def get_slot_priority(
    primary: IntentCategory,
    secondary: IntentAction,
    slot_name: str,
) -> SlotPriority | None:
    """获取槽位优先级"""
    primary_key = primary.value
    secondary_key = secondary.value

    if primary_key not in SLOT_PRIORITY_CONFIG:
        return None
    if secondary_key not in SLOT_PRIORITY_CONFIG[primary_key]:
        return None

    config = SLOT_PRIORITY_CONFIG[primary_key][secondary_key]

    for priority_level, slots in config.items():
        if slot_name in slots:
            return SlotPriority(priority_level)

    return None


def get_required_slots(
    primary: IntentCategory,
    secondary: IntentAction,
) -> list[str]:
    """获取指定意图组合的所有必需槽位（P0）"""
    primary_key = primary.value
    secondary_key = secondary.value

    if primary_key not in SLOT_PRIORITY_CONFIG:
        return []
    if secondary_key not in SLOT_PRIORITY_CONFIG[primary_key]:
        return []

    return SLOT_PRIORITY_CONFIG[primary_key][secondary_key].get("P0", [])


def check_intent_compatibility(
    current_intent: str,
    new_intent: str,
) -> bool:
    """检查两个意图之间是否可以平滑切换"""
    # 相同意图总是兼容
    if current_intent == new_intent:
        return True

    # 检查兼容性矩阵
    if current_intent in INTENT_COMPATIBILITY:
        return new_intent in INTENT_COMPATIBILITY[current_intent]

    # 反向检查
    if new_intent in INTENT_COMPATIBILITY:
        return current_intent in INTENT_COMPATIBILITY[new_intent]

    return False
```

- [ ] **Step 2: 编写配置测试**

创建 `tests/intent/test_config.py`:

```python
"""测试意图配置"""

import pytest
from app.intent.config import (
    TERTIARY_INTENT_CONFIG,
    SLOT_PRIORITY_CONFIG,
    INTENT_COMPATIBILITY,
    validate_tertiary_intent,
    get_slot_priority,
    get_required_slots,
    check_intent_compatibility,
)
from app.intent.models import IntentCategory, IntentAction, SlotPriority


def test_tertiary_intent_config_exists():
    assert ("AFTER_SALES", "APPLY") in TERTIARY_INTENT_CONFIG
    assert ("ORDER", "QUERY") in TERTIARY_INTENT_CONFIG


def test_validate_tertiary_intent_valid():
    result = validate_tertiary_intent(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "REFUND",
    )
    assert result is True


def test_validate_tertiary_intent_invalid():
    result = validate_tertiary_intent(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "INVALID_INTENT",
    )
    assert result is False


def test_validate_tertiary_intent_none():
    result = validate_tertiary_intent(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        None,
    )
    assert result is True


def test_get_slot_priority_p0():
    priority = get_slot_priority(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "order_sn",
    )
    assert priority == SlotPriority.P0


def test_get_slot_priority_p1():
    priority = get_slot_priority(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "reason_category",
    )
    assert priority == SlotPriority.P1


def test_get_slot_priority_not_found():
    priority = get_slot_priority(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "nonexistent_slot",
    )
    assert priority is None


def test_get_required_slots():
    slots = get_required_slots(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
    )
    assert "order_sn" in slots
    assert "action_type" in slots


def test_check_intent_compatibility_same():
    result = check_intent_compatibility(
        "ORDER/QUERY",
        "ORDER/QUERY",
    )
    assert result is True


def test_check_intent_compatibility_compatible():
    result = check_intent_compatibility(
        "AFTER_SALES/APPLY",
        "AFTER_SALES/CONSULT",
    )
    assert result is True


def test_check_intent_compatibility_incompatible():
    result = check_intent_compatibility(
        "ORDER/QUERY",
        "ACCOUNT/QUERY",
    )
    assert result is False
```

- [ ] **Step 3: 运行配置测试**

```bash
python -m pytest tests/intent/test_config.py -v
```

Expected: 所有测试通过

- [ ] **Step 4: Commit**

```bash
git add app/intent/config.py tests/intent/test_config.py
git commit -m "feat(intent): 添加意图配置系统

- 定义意图兼容性矩阵INTENT_COMPATIBILITY
- 定义三级意图约束TERTIARY_INTENT_CONFIG
- 实现槽位优先级配置SLOT_PRIORITY_CONFIG
- 添加配置验证函数和查询函数
- 添加配置单元测试

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 实现意图分类器（Function Calling）

**Files:**
- Create: `app/intent/classifier.py`
- Test: `tests/intent/test_classifier.py`

### 步骤1: 实现分类器

- [ ] **Step 1: 编写意图分类器**

(由于篇幅限制，分类器实现代码参见设计文档第8节)

- [ ] **Step 2: 编写分类器测试**

创建 `tests/intent/test_classifier.py`，测试以下场景：
1. 标准意图识别（ORDER, AFTER_SALES, POLICY等）
2. 槽位提取（order_sn, product_name等）
3. 三级意图验证
4. 异常情况处理（LLM调用失败）

- [ ] **Step 3: Commit**

```bash
git add app/intent/classifier.py tests/intent/test_classifier.py
git commit -m "feat(intent): 实现意图分类器（Function Calling）

- 使用OpenAI Function Calling进行分层意图识别
- 支持12个一级意图、8个二级动作
- 集成Few-shot示例提升准确率
- 添加三级意图验证
- 完善的错误处理

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4-9: 其他核心组件

**Task 4: 槽位验证器** (`app/intent/slot_validator.py`)
- 检查槽位完整性
- 按P0/P1/P2优先级管理
- 识别缺失槽位

**Task 5: 澄清引擎** (`app/intent/clarification.py`)
- 生成渐进式追问问题
- 智能推荐候选值
- 处理用户拒绝（4种降级策略）

**Task 6: 话题切换检测** (`app/intent/topic_switch.py`)
- 显式切换检测（关键词）
- 隐式切换检测（置信度下降）
- 意图兼容性检查

**Task 7: 多意图处理** (`app/intent/multi_intent.py`)
- 意图拆分（基于分隔符+LLM确认）
- 槽位共享机制
- 优先级排序和执行

**Task 8: 安全过滤** (`app/intent/safety.py`)
- 关键词过滤
- Prompt注入检测
- LLM语义安全检测

**Task 9: 服务层** (`app/intent/service.py`)
- 整合所有组件
- 对外提供统一接口
- 会话状态管理

---

## Task 10: 替换RouterAgent

**Files:**
- Modify: `app/agents/router.py`
- Modify: `app/agents/__init__.py`

### 步骤1: 实现新的IntentRouterAgent

- [ ] **Step 1: 重写RouterAgent**

使用新的意图识别系统替换现有的规则+LLM混合方案：

```python
"""新的意图路由Agent

使用分层意图识别系统替换原有的规则+LLM混合方案。
"""

from app.agents.base import AgentResult, BaseAgent
from app.intent import IntentRecognitionService, IntentCategory


class IntentRouterAgent(BaseAgent):
    """
    意图路由Agent（v2.0）

    基于Function Calling的分层意图识别：
    1. 识别一级（业务域）、二级（动作）、三级（子意图）
    2. 槽位提取和验证
    3. 智能澄清机制
    4. 话题切换检测
    """

    def __init__(self):
        super().__init__(name="intent_router", system_prompt=None)
        self.intent_service = IntentRecognitionService()

    async def process(self, state: dict) -> AgentResult:
        """
        处理用户输入，识别意图并路由

        流程：
        1. 检测话题切换
        2. 识别用户意图（Function Calling）
        3. 验证槽位完整性
        4. 需要澄清 -> 生成追问问题
        5. 意图清晰 -> 路由到对应Agent
        """
        query = state.get("question", "")
        session_id = state.get("thread_id", "")
        user_id = state.get("user_id")

        # 1. 话题切换检测
        if await self._detect_topic_switch(state):
            await self._handle_topic_switch(session_id)

        # 2. 意图识别
        result = await self.intent_service.recognize(
            query=query,
            session_id=session_id,
            conversation_history=state.get("history", []),
        )

        # 3. 需要澄清
        if result.needs_clarification or result.missing_slots:
            clarification = await self.intent_service.clarify(
                session_id=session_id,
                user_response=query,
            )
            return AgentResult(
                response=clarification.response,
                updated_state={
                    "awaiting_clarification": True,
                    "clarification_state": clarification.state,
                }
            )

        # 4. 意图清晰，路由到对应Agent
        next_agent = self._route_by_intent(result)

        return AgentResult(
            response="",  # 由下一个Agent生成
            updated_state={
                "intent_result": result.to_dict(),
                "next_agent": next_agent,
                "slots": result.slots,
            }
        )

    def _route_by_intent(self, result) -> str:
        """根据意图路由到对应Agent"""
        routing_map = {
            IntentCategory.ORDER: "order",
            IntentCategory.AFTER_SALES: "order",
            IntentCategory.POLICY: "policy",
            IntentCategory.PRODUCT: "policy",  # 商品咨询也走policy
            IntentCategory.RECOMMENDATION: "policy",
            IntentCategory.CART: "order",
        }
        return routing_map.get(result.primary_intent, "supervisor")
```

- [ ] **Step 2: 更新agents/__init__.py**

```python
# app/agents/__init__.py

from app.agents.router import IntentRouterAgent
from app.agents.order import OrderAgent
from app.agents.policy import PolicyAgent
from app.agents.supervisor import SupervisorAgent

__all__ = [
    "IntentRouterAgent",
    "OrderAgent",
    "PolicyAgent",
    "SupervisorAgent",
]
```

- [ ] **Step 3: 更新supervisor.py使用新的Router**

修改 `app/agents/supervisor.py`，将 `RouterAgent` 替换为 `IntentRouterAgent`。

- [ ] **Step 4: Commit**

```bash
git add app/agents/router.py app/agents/__init__.py app/agents/supervisor.py
git commit -m "feat(intent): 集成新的意图识别系统

- 重写RouterAgent使用IntentRecognitionService
- 支持分层意图路由
- 集成槽位验证和澄清机制
- 更新SupervisorAgent使用新Router

BREAKING CHANGE: RouterAgent接口保持不变，内部实现完全替换

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## 测试策略

### 集成测试

创建 `tests/intent/test_integration.py`：

```python
"""意图识别集成测试"""

import pytest
from app.intent import IntentRecognitionService


class TestIntentRecognitionIntegration:
    """端到端意图识别测试"""

    @pytest.fixture
    async def service(self):
        return IntentRecognitionService()

    async def test_order_query(self, service):
        """测试订单查询场景"""
        result = await service.recognize(
            query="查一下我的订单",
            session_id="test_1"
        )
        assert result.primary_intent.value == "ORDER"
        assert result.secondary_intent.value == "QUERY"
        assert result.confidence > 0.7

    async def test_refund_apply(self, service):
        """测试退货申请场景"""
        result = await service.recognize(
            query="我要退货，订单SN001",
            session_id="test_2"
        )
        assert result.primary_intent.value == "AFTER_SALES"
        assert result.secondary_intent.value == "APPLY"
        assert "order_sn" in result.slots

    async def test_clarification_flow(self, service):
        """测试澄清流程"""
        # 第一轮：缺少订单号
        result1 = await service.recognize(
            query="我要退货",
            session_id="test_3"
        )
        assert result1.needs_clarification is True

        # 第二轮：提供订单号
        result2 = await service.clarify(
            session_id="test_3",
            user_response="订单SN001"
        )
        assert "order_sn" in result2.collected_slots
```

---

## 执行检查清单

### 实施前准备
- [ ] 确认OpenAI API Key可用
- [ ] 确认模型支持Function Calling
- [ ] 备份现有router.py

### 实施顺序
建议按Task 1-10顺序实施，每个Task完成后再进入下一个。

### 回滚策略
如遇到问题，可通过以下命令回滚：
```bash
git revert HEAD~n  # n为实施的commit数量
```

---

## 计划完成总结

**文档位置**: `docs/superpowers/plans/2025-01-09-intent-recognition-implementation.md`

**计划覆盖**:
- ✅ Task 1-2: 基础结构和配置系统（详细步骤）
- ✅ Task 3-9: 核心组件实现（概要说明）
- ✅ Task 10: RouterAgent替换
- ✅ 测试策略

**预估工作量**: 8-12小时（按Task逐个实施）

**关键风险**:
1. Function Calling稳定性（有fallback方案）
2. 与现有系统集成复杂度（接口兼容）

---

## 执行方式选择

**Plan complete and saved to `docs/superpowers/plans/2025-01-09-intent-recognition-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review

**Which approach?**