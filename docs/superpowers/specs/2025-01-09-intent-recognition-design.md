# 意图识别系统重构设计文档

**日期**: 2025-01-09
**版本**: v1.0
**作者**: AI Assistant
**状态**: 待评审

---

## 1. 背景与目标

### 1.1 当前问题

现有系统的意图识别采用**规则+LLM混合**方案，存在以下问题：

1. **规则优先导致误判**：关键词匹配优先于语义理解
   - 示例："我不想退货了" → 匹配"退货" → 错误路由到退货流程
2. **单一层级分类**：无法表达复杂意图（如"售后场景的退货政策咨询"）
3. **无澄清机制**：不确定时直接分类为OTHER或猜测，用户体验差
4. **槽位管理缺失**：多轮对话中无法有效收集必要信息

### 1.2 设计目标

1. **准确率提升至95%+**（当前约70%）
2. **支持分层意图表达**（一级业务域 + 二级动作 + 可选三级子意图）
3. **实现智能澄清机制**（渐进式追问 + 智能推荐）
4. **支持槽位填充与管理**（按优先级渐进收集）
5. **优雅处理边界情况**（多意图、意图冲突、无法识别等）

---

## 2. 分层意图体系

### 2.1 意图层级定义

```yaml
一级（业务域 - Primary Intent）:
  - ORDER: 订单相关（查询、修改、取消）
  - AFTER_SALES: 售后服务（退货、换货、维修）
  - POLICY: 平台政策咨询（运费、退货政策、时效）
  - ACCOUNT: 账户相关（登录、密码、个人信息）
  - PROMOTION: 营销优惠（优惠券、活动、积分）
  - PAYMENT: 支付相关（支付方式、发票、退款到账）
  - LOGISTICS: 物流相关（查询、修改地址、催件）
  - COMPLAINT: 投诉建议
  - OTHER: 其他（寒暄、无关问题）

二级（动作类型 - Secondary Intent）:
  - QUERY: 查询状态/信息
  - APPLY: 申请办理
  - MODIFY: 修改信息
  - CANCEL: 取消操作
  - CONSULT: 一般咨询（无需具体操作）

三级（子意图 - Tertiary Intent，可选）:
  # AFTER_SALES 场景
  - REFUND_SHIPPING_FEE: 退货运费咨询
  - REFUND_TIMELINE: 退款到账时间
  - EXCHANGE_SIZE: 换货尺码问题

  # ORDER 场景
  - ORDER_TRACKING_DETAIL: 物流轨迹详情
  - ORDER_STATUS_ESTIMATE: 预计送达时间

  # POLICY 场景
  - POLICY_RETURN_EXCEPTION: 特殊商品退货政策
  - POLICY_SHIPPING_FEE: 运费计算规则
```

### 2.2 意图组合示例

| 用户输入 | 一级 | 二级 | 三级 | 说明 |
|---------|------|------|------|------|
| "查一下我的订单" | ORDER | QUERY | null | 简单查询 |
| "我要退货，订单SN001" | AFTER_SALES | APPLY | null | 退货申请 |
| "退货的运费谁出" | AFTER_SALES | CONSULT | REFUND_SHIPPING_FEE | 政策咨询 |
| "退款多久到账" | AFTER_SALES | CONSULT | REFUND_TIMELINE | 时效咨询 |
| "内衣可以退吗" | POLICY | CONSULT | POLICY_RETURN_EXCEPTION | 特殊商品政策 |
| "优惠券怎么用" | PROMOTION | CONSULT | null | 营销活动咨询 |

---

## 3. 系统架构

### 3.1 组件图

```
┌─────────────────────────────────────────────────────────────┐
│                    Intent Recognition System                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐     ┌─────────────────────────────┐   │
│  │  Query Analyzer │────▶│  Intent Classifier          │   │
│  │  (预处理)       │     │  (Function Calling + Few-shot)│ │
│  └─────────────────┘     └──────────────┬──────────────┘   │
│                                         │                  │
│                                         ▼                  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              Intent Resolution Result                │  │
│  │  {                                                   │  │
│  │    primary_intent,                                   │  │
│  │    secondary_intent,                                 │  │
│  │    tertiary_intent,                                  │  │
│  │    confidence,                                       │  │
│  │    slots,                                            │  │
│  │    needs_clarification,                              │  │
│  │    ambiguity_type                                    │  │
│  │  }                                                   │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                         │                                  │
│         ┌───────────────┼───────────────┐                  │
│         ▼               ▼               ▼                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Slot        │ │ Intent      │ │ Topic       │          │
│  │ Validator   │ │ Confirmer   │ │ Switch      │          │
│  │ (槽位检查)   │ │ (意图确认)   │ │ Detector    │          │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘          │
│         │               │               │                  │
│         └───────────────┼───────────────┘                  │
│                         ▼                                  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │           Clarification Engine (澄清引擎)            │  │
│  │  - Progressive追问策略                               │  │
│  │  - 智能推荐辅助                                       │  │
│  │  - 槽位优先级管理                                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件职责

#### 3.2.1 IntentClassifier（意图分类器）

**职责**：基于Function Calling进行意图识别

**输入**：
- 当前用户query
- 对话历史（最近3轮）
- 当前槽位状态

**输出**：`IntentResolutionResult`（结构化意图解析结果）

**实现要点**：
- 使用OpenAI Function Calling定义意图schema
- Few-shot示例包含在system prompt中（10-15个典型示例）
- 支持槽位预抽取（从query中直接提取订单号、商品名等）

#### 3.2.2 SlotValidator（槽位验证器）

**职责**：检查当前意图所需的槽位是否完整

**槽位优先级定义**：

```python
SLOT_PRIORITIES = {
    "AFTER_SALES": {
        "APPLY": {
            "P0": ["order_sn"],                    # 必须
            "P1": ["action_type", "reason_category"],  # 重要
            "P2": ["reason_detail", "preferred_contact"]  # 可选
        },
        "CONSULT": {
            "P0": ["policy_topic"],
            "P1": ["specific_item"],
            "P2": []
        }
    },
    "ORDER": {
        "QUERY": {
            "P0": ["order_sn"],  # 可为"最近订单"
            "P1": ["query_type"],
            "P2": []
        }
    },
    # ... 其他意图组合
}
```

#### 3.2.3 TopicSwitchDetector（话题切换检测器）

**职责**：检测用户是否切换了话题

**检测策略**：
1. **显式标记检测**（高优先级）：
   - 关键词："换个问题"、"另外"、"对了"、"再问一下"
   - 检测规则：正则匹配显式切换词

2. **置信度下降检测**（辅助）：
   - 当前query与上轮意图的匹配置信度 < 0.5
   - 触发重新识别

3. **意图冲突检测**：
   - 新query匹配到的意图与当前意图不兼容
   - 示例：当前在退货流程，用户突然问"优惠券怎么领"

#### 3.2.4 ClarificationEngine（澄清引擎）

**职责**：在槽位缺失或意图不确定时，生成澄清问题

**澄清策略**：
1. **渐进式追问**：一次只问一个槽位，按优先级从高到低
2. **智能推荐**：对高价值槽位（如订单号），优先推荐候选值让用户确认
3. **选项引导**：对分类型槽位（如退货原因），提供选项A/B/C

**最大追问次数**：3轮，超过则转人工

---

## 4. 数据模型

### 4.1 IntentResolutionResult（意图解析结果）

```python
class IntentResolutionResult(BaseModel):
    """意图解析结果"""

    # === 意图层级 ===
    primary_intent: str           # 一级意图（业务域）
    secondary_intent: str         # 二级意图（动作类型）
    tertiary_intent: str | None   # 三级意图（子意图，可选）

    # === 置信度 ===
    confidence: float             # 总体置信度 (0-1)
    intent_confidences: dict      # 各级意图的置信度

    # === 槽位信息 ===
    slots: dict                   # 已提取的槽位 {slot_name: value}
    required_slots: list          # 当前意图必需的槽位列表
    missing_slots: list           # 缺失的槽位列表（按优先级排序）

    # === 澄清相关 ===
    needs_clarification: bool     # 是否需要澄清
    ambiguity_type: str | None    # 歧义类型："missing_slots" / "intent_conflict" / "low_confidence"
    clarification_question: str | None  # 生成的澄清问题

    # === 原始信息 ===
    raw_query: str                # 原始用户输入
    matched_patterns: list        # 匹配到的模式/示例

class ClarificationState(BaseModel):
    """澄清状态（用于多轮对话追踪）"""

    session_id: str
    current_intent: IntentResolutionResult
    clarification_round: int      # 当前澄清轮次（最大3轮）
    asked_slots: list             # 已经询问过的槽位
    collected_slots: dict         # 已收集的槽位
    pending_slot: str | None      # 当前待确认的槽位
    clarification_history: list   # 澄清历史记录
```

### 4.2 意图Schema（Function Calling定义）

```python
INTENT_FUNCTION_SCHEMA = {
    "name": "resolve_intent",
    "description": "解析用户意图并提取相关槽位",
    "parameters": {
        "type": "object",
        "properties": {
            "primary_intent": {
                "type": "string",
                "enum": ["ORDER", "AFTER_SALES", "POLICY", "ACCOUNT",
                        "PROMOTION", "PAYMENT", "LOGISTICS", "COMPLAINT", "OTHER"],
                "description": "一级意图：业务域"
            },
            "secondary_intent": {
                "type": "string",
                "enum": ["QUERY", "APPLY", "MODIFY", "CANCEL", "CONSULT"],
                "description": "二级意图：动作类型"
            },
            "tertiary_intent": {
                "type": "string",
                "description": "三级意图：具体子意图（如有）"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "意图识别的置信度"
            },
            "slots": {
                "type": "object",
                "properties": {
                    "order_sn": {"type": "string"},
                    "action_type": {"type": "string", "enum": ["REFUND", "EXCHANGE", "REPAIR"]},
                    "reason_category": {"type": "string"},
                    "policy_topic": {"type": "string"},
                    "query_type": {"type": "string"},
                    # ... 其他槽位
                }
            },
            "needs_clarification": {
                "type": "boolean",
                "description": "是否需要进一步澄清"
            },
            "ambiguity_reason": {
                "type": "string",
                "description": "如果需要澄清，说明原因"
            }
        },
        "required": ["primary_intent", "secondary_intent", "confidence", "slots", "needs_clarification"]
    }
}
```

---

## 5. 核心流程

### 5.1 主流程：意图识别与处理

```
┌─────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 用户输入 │────▶│ 话题切换检测     │────▶│ 意图分类器      │
└─────────┘     │ (显式/隐式)     │     │ (Function Call) │
                └────────┬────────┘     └────────┬────────┘
                         │                       │
                         │    检测到切换         │
                         │◀──────────────────────┤
                         │                       │
                         ▼                       ▼
                ┌─────────────────┐     ┌─────────────────┐
                │ 重置对话状态     │     │ 槽位验证器      │
                │ (保持历史)      │     │ (检查完整性)    │
                └─────────────────┘     └────────┬────────┘
                                                 │
                              ┌──────────────────┼──────────────────┐
                              │                  │                  │
                              ▼                  ▼                  ▼
                        ┌─────────┐      ┌─────────────┐     ┌─────────────┐
                        │ 槽位完整 │      │ 缺失P0槽位   │     │ 缺失P1/P2   │
                        │ (无缺失) │      │ (必须追问)   │     │ (可选追问)  │
                        └────┬────┘      └──────┬──────┘     └──────┬──────┘
                             │                  │                  │
                             ▼                  ▼                  ▼
                        ┌─────────┐      ┌─────────────┐     ┌─────────────┐
                        │ 执行意图 │      │ 澄清引擎     │     │ 澄清引擎     │
                        │ 对应动作 │      │ (渐进追问)   │     │ (智能推荐)   │
                        └─────────┘      └─────────────┘     └─────────────┘
```

### 5.2 澄清流程

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 检测到缺失   │────▶│ 选择优先级最高   │────▶│ 生成澄清问题    │
│ 槽位        │     │ 的缺失槽位       │     │                 │
└─────────────┘     └─────────────────┘     └────────┬────────┘
                                                     │
                              ┌──────────────────────┼──────────────────────┐
                              │                      │                      │
                              ▼                      ▼                      ▼
                        ┌─────────┐          ┌─────────────┐         ┌─────────────┐
                        │ 订单号   │          │ 分类型槽位   │         │ 其他槽位    │
                        │ (P0)    │          │ (原因等)    │         │             │
                        └────┬────┘          └──────┬──────┘         └──────┬──────┘
                             │                      │                      │
                             ▼                      ▼                      ▼
                  ┌─────────────────────┐   ┌─────────────────┐   ┌─────────────────┐
                  │ 智能推荐候选订单     │   │ 提供选项A/B/C   │   │ 开放式提问      │
                  │ "是要退SN001吗？"   │   │ "原因是？A..."  │   │ "请描述..."    │
                  └─────────────────────┘   └─────────────────┘   └─────────────────┘
                                                     │
                                                     ▼
                                            ┌─────────────────┐
                                            │ 发送澄清问题     │
                                            │ 等待用户回复     │
                                            └─────────────────┘
```

### 5.3 多意图处理流程

```
用户输入: "查订单SN001，顺便问下退货要多久"

┌────────────────────────────────────────────────────────────────┐
│ Step 1: 多意图检测                                               │
│ - 使用分隔符检测（"顺便"、"还有"、"另外"）                         │
│ - 或基于置信度分布（多个意图置信度都>0.6）                         │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Step 2: 意图分解                                                │
│ Input: "查订单SN001，顺便问下退货要多久"                          │
│ Output:                                                        │
│   - Intent 1: ORDER/QUERY (order_sn=SN001)                     │
│   - Intent 2: AFTER_SALES/CONSULT/REFUND_TIMELINE              │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Step 3: 优先级排序（根据业务规则）                                 │
│ - 查询类优先于申请类（先查后办）                                  │
│ - 当前流程中的意图优先                                           │
│ Result: ORDER/QUERY → AFTER_SALES/CONSULT                      │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Step 4: 依次执行                                                 │
│ - 先处理订单查询                                                 │
│ - 在处理结果后，自动处理退货时效咨询                               │
│ - 或询问用户："先帮您查询订单，然后回答退货时效问题，可以吗？"       │
└────────────────────────────────────────────────────────────────┘
```

---

## 6. 边界情况处理

### 6.1 情况对照表

| 情况 | 检测条件 | 处理策略 | 示例 |
|------|---------|---------|------|
| **无法识别** | confidence < 0.3 | 礼貌回复+建议可咨询范围 | "我不太理解，您可以问订单、退货或政策相关问题" |
| **意图冲突** | 多个意图置信度差<0.2 | 主动让用户选择 | "您是要查询订单，还是申请退货？" |
| **敏感内容** | 命中安全关键词 | 触发安全过滤，礼貌结束 | "抱歉，我无法回答这个问题" |
| **重复追问** | 同一槽位追问>2次 | 提供跳过/转人工选项 | "您可以跳过此问题，或转接人工客服" |
| **槽位无效** | 用户提供值格式错误 | 提示正确格式，重新询问 | "订单号格式应为SN开头，请重新提供" |
| **意图漂移** | 中间轮次突然切换 | 确认是否切换，保存原状态 | "是否改为咨询退货政策？之前的退货申请将暂存" |
| **过度澄清** | 澄清轮次>=3 | 转人工或智能猜测 | "我将根据已有信息为您处理..." |

### 6.2 安全过滤

```python
SAFETY_RULES = {
    "blocked_keywords": [
        # 辱骂词汇
        "脏话列表...",
        # 敏感政治词汇
        "政治敏感词...",
    ],
    "action": "block_and_escalate",  # 拦截并升级
    "response": "抱歉，我无法回答这个问题。如有其他问题，请联系人工客服。"
}
```

---

## 7. 提示词设计

### 7.1 System Prompt（精简版）

```
你是电商客服意图识别专家。分析用户输入，识别其真实意图。

## 意图层级
一级（业务域）：ORDER(订单), AFTER_SALES(售后), POLICY(政策), ACCOUNT(账户), PROMOTION(优惠), PAYMENT(支付), LOGISTICS(物流), COMPLAINT(投诉), OTHER(其他)
二级（动作）：QUERY(查询), APPLY(申请), MODIFY(修改), CANCEL(取消), CONSULT(咨询)
三级（子意图）：根据上下文判断，如REFUND_SHIPPING_FEE(退货运费), REFUND_TIMELINE(退款时效)等

## 槽位提取规则
- order_sn: 订单号格式为"SN"+数字，如SN20240001
- action_type: 退货/换货/维修
- reason_category: 质量问题/尺码不合适/与描述不符/不想要了/其他

## 示例（Few-shot）
用户: "我的订单到哪了"
→ primary: ORDER, secondary: QUERY, slots: {query_type: "物流状态"}

用户: "我要退货，订单SN001，质量问题"
→ primary: AFTER_SALES, secondary: APPLY, slots: {order_sn: "SN001", reason_category: "质量问题"}

用户: "退货的运费谁出"
→ primary: AFTER_SALES, secondary: CONSULT, tertiary: REFUND_SHIPPING_FEE

## 输出要求
- 必须调用resolve_intent函数
- confidence: 0-1之间的置信度
- needs_clarification: 槽位缺失或置信度<0.7时为true
```

---

## 8. 接口定义

### 8.1 对外接口

```python
class IntentRecognitionService:
    """意图识别服务"""

    async def recognize(
        self,
        query: str,
        session_id: str,
        conversation_history: list[dict] | None = None,
        current_state: ClarificationState | None = None
    ) -> IntentRecognitionResult:
        """
        识别用户意图

        Args:
            query: 用户输入
            session_id: 会话ID
            conversation_history: 对话历史（最近3轮）
            current_state: 当前澄清状态（如果有）

        Returns:
            IntentRecognitionResult: 包含意图、槽位、澄清需求等
        """
        pass

    async def clarify(
        self,
        session_id: str,
        user_response: str,
        current_state: ClarificationState
    ) -> ClarificationResult:
        """
        处理澄清回复，更新槽位状态

        Args:
            session_id: 会话ID
            user_response: 用户对澄清问题的回复
            current_state: 当前澄清状态

        Returns:
            ClarificationResult: 更新后的状态，是否继续澄清等
        """
        pass
```

### 8.2 与现有系统集成

```python
# 替换现有的 RouterAgent
class IntentRouterAgent(BaseAgent):
    """新的意图路由Agent（替换原RouterAgent）"""

    def __init__(self):
        self.intent_service = IntentRecognitionService()
        self.clarification_states: dict[str, ClarificationState] = {}

    async def process(self, state: dict) -> AgentResult:
        query = state.get("question", "")
        session_id = state.get("thread_id", "")
        user_id = state.get("user_id")

        # 检查是否有未完成的澄清
        current_state = self.clarification_states.get(session_id)

        if current_state and current_state.pending_slot:
            # 处理澄清回复
            result = await self.intent_service.clarify(
                session_id, query, current_state
            )
        else:
            # 新的意图识别
            result = await self.intent_service.recognize(
                query=query,
                session_id=session_id,
                conversation_history=state.get("history", [])
            )

        # 处理识别结果...
        if result.needs_clarification:
            # 保存澄清状态
            self.clarification_states[session_id] = result.clarification_state
            return AgentResult(
                response=result.clarification_question,
                updated_state={"awaiting_clarification": True}
            )

        # 意图清晰，路由到对应Agent
        next_agent = self._route_to_agent(result)
        return AgentResult(
            response="",  # 由下一个Agent生成
            updated_state={
                "intent_result": result,
                "next_agent": next_agent,
                "slots": result.slots
            }
        )
```

---

## 9. 测试策略

### 9.1 测试用例分类

| 类别 | 测试数量 | 覆盖场景 |
|------|---------|---------|
| 单意图识别 | 50+ | 各一级+二级意图组合 |
| 槽位提取 | 30+ | 订单号、原因、商品名等 |
| 多意图分解 | 20+ | 2-3个意图的组合输入 |
| 澄清流程 | 20+ | 各槽位类型的渐进追问 |
| 边界情况 | 20+ | 无法识别、意图冲突、敏感内容等 |
| 话题切换 | 15+ | 显式/隐式切换检测 |

### 9.2 关键测试用例示例

```python
# 测试用例：多意图识别
{
    "input": "查一下SN001订单，顺便问一下退货要多久，还有你们电话多少",
    "expected": {
        "intents": [
            {"primary": "ORDER", "secondary": "QUERY", "slots": {"order_sn": "SN001"}},
            {"primary": "AFTER_SALES", "secondary": "CONSULT", "tertiary": "REFUND_TIMELINE"},
            {"primary": "OTHER", "secondary": "CONSULT"}  # 客服电话
        ],
        "priority": [0, 1, 2]  # 执行顺序
    }
}

# 测试用例：隐含意图
{
    "input": "这个质量真的'不错'，穿一次就破了",
    "expected": {
        "primary": "AFTER_SALES",
        "secondary": "APPLY",
        "tertiary": "REFUND_QUALITY_ISSUE",
        "sentiment": "negative_sarcasm",  # 讽刺检测
        "confidence": ">0.8"
    }
}
```

---

## 10. 性能与成本预估

### 10.1 Token消耗估算

| 场景 | Input Tokens | Output Tokens | 单次成本(¥) |
|------|-------------|---------------|------------|
| 标准意图识别 | 800-1200 | 200-400 | ~0.015 |
| 带Few-shot | 1500-2000 | 200-400 | ~0.025 |
| 澄清回合 | 1000-1500 | 150-300 | ~0.018 |

### 10.2 响应时间预估

| 指标 | 目标值 | 备注 |
|------|--------|------|
| 意图识别 | <500ms | Function Calling延迟 |
| 澄清生成 | <300ms | 模板渲染+简单逻辑 |
| 端到端 | <1s | 包含网络传输 |

### 10.3 准确率目标

| 指标 | 当前 | 目标 | 验证方式 |
|------|------|------|---------|
| 一级意图准确率 | ~75% | >95% | 人工标注1000条 |
| 二级意图准确率 | ~70% | >92% | 人工标注1000条 |
| 槽位提取F1 | ~60% | >88% | 精确率+召回率 |
| 澄清成功率 | N/A | >80% | 用户完成槽位填充比例 |

---

## 11. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Function Calling不稳定 | 中 | 高 | 实现fallback到JSON模式 |
| 意图分类过细导致混淆 | 中 | 中 | 提供详细的边界定义文档 |
| 槽位优先级不符合业务 | 低 | 高 | 与业务方确认优先级规则 |
| 多意图处理复杂度超预期 | 中 | 中 | MVP阶段限制最多2个意图 |
| 响应时间不达标 | 低 | 高 | 实现缓存+异步预处理 |

---

## 12. 附录

### 12.1 术语表

| 术语 | 定义 |
|------|------|
| 意图(Intent) | 用户输入的目的或目标 |
| 槽位(Slot) | 完成意图所需的具体信息片段 |
| 澄清(Clarification) | 系统主动提问以获取缺失信息 |
| Few-shot | 在Prompt中提供示例以引导模型 |
| Function Calling | LLM通过调用预定义函数输出结构化数据 |

### 12.2 参考文献

1. OpenAI Function Calling Documentation
2. 阿里云小蜜意图设计最佳实践
3. Rasa对话系统意图分类设计指南

---

## 13. 评审记录

| 日期 | 评审人 | 意见 | 状态 |
|------|--------|------|------|
| | | | |

---

**文档状态**: 待评审
**下次评审日期**: 待确定
