# 意图识别系统重构设计文档

**日期**: 2025-01-09
**版本**: v1.1
**作者**: AI Assistant
**状态**: 待评审

**v1.1更新说明**: 补充意图分类体系、完善话题切换检测、增强安全过滤、新增数据隐私与人工介入机制等

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
  - PRODUCT: 商品相关（库存、规格、详情、比价）         # v1.1新增
  - RECOMMENDATION: 商品推荐                           # v1.1新增
  - CART: 购物车操作                                   # v1.1新增
  - COMPLAINT: 投诉建议
  - OTHER: 其他（寒暄、无关问题）

二级（动作类型 - Secondary Intent）:
  - QUERY: 查询状态/信息
  - APPLY: 申请办理
  - MODIFY: 修改信息
  - CANCEL: 取消操作
  - CONSULT: 一般咨询（无需具体操作）
  - ADD: 添加/加入                                     # v1.1新增（适用于CART等）
  - REMOVE: 移除/删除                                  # v1.1新增（适用于CART等）
  - COMPARE: 比较                                      # v1.1新增（适用于PRODUCT等）

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

  # PRODUCT 场景（v1.1新增）
  - PRODUCT_STOCK: 商品库存查询
  - PRODUCT_SPEC: 商品规格咨询
  - PRODUCT_DETAIL: 商品详情查看
  - PRODUCT_PRICE_COMPARE: 商品价格比较
  - PRODUCT_REVIEW: 商品评价查看

  # RECOMMENDATION 场景（v1.1新增）
  - RECOMMEND_SIMILAR: 相似商品推荐
  - RECOMMEND_COMPLEMENTARY: 搭配商品推荐
  - RECOMMEND_PERSONALIZED: 个性化推荐
  - RECOMMEND_TRENDING: 热销商品推荐

  # CART 场景（v1.1新增）
  - CART_VIEW: 查看购物车
  - CART_CHECKOUT: 购物车结算
  - CART_REMOVE_ITEM: 选择并移除特定商品  # v1.1 fix: 重命名以更准确表达意图
  - CART_CLEAR_ALL: 清空购物车           # v1.1 fix: 新增三级意图
  - CART_UPDATE_QUANTITY: 修改商品数量
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
| "这款商品有货吗" | PRODUCT | QUERY | PRODUCT_STOCK | 库存查询（v1.1新增） |
| "给我推荐几款手机" | RECOMMENDATION | QUERY | RECOMMEND_PERSONALIZED | 个性化推荐（v1.1新增） |
| "把这件加入购物车" | CART | ADD | null | 添加购物车（v1.1新增） |
| "帮我看看购物车" | CART | QUERY | CART_VIEW | 查看购物车（v1.1新增） |
| "比较一下这两款手机" | PRODUCT | COMPARE | PRODUCT_PRICE_COMPARE | 商品比价（v1.1新增） |

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

**槽位优先级配置化设计**（v1.1增强）：

```python
from enum import Enum
from typing import Protocol


class SlotPriorityConfigSource(Protocol):
    """槽位优先级配置源协议"""

    async def get_config(
        self,
        primary_intent: str,
        secondary_intent: str,
        user_profile: dict | None = None
    ) -> SlotPriorityConfig:
        """获取槽位优先级配置"""
        ...


class ConfigurableSlotValidator:
    """可配置化槽位验证器（v1.1新增）"""

    def __init__(
        self,
        config_source: SlotPriorityConfigSource,
        ab_test_service: ABTestService | None = None
    ):
        self.config_source = config_source
        self.ab_test_service = ab_test_service
        self._cache: dict[str, SlotPriorityConfig] = {}

    async def validate(
        self,
        intent: IntentResolutionResult,
        user_id: str | None = None,
        user_profile: dict | None = None
    ) -> ValidationResult:
        """验证槽位完整性"""
        # 获取配置（支持A/B测试）
        config = await self._get_config_with_ab_test(
            intent.primary_intent,
            intent.secondary_intent,
            user_id,
            user_profile
        )

        # 按优先级检查槽位
        missing_by_priority = {"P0": [], "P1": [], "P2": []}

        for priority in ["P0", "P1", "P2"]:
            for slot_name in config.slots.get(priority, []):
                if slot_name not in intent.slots or intent.slots[slot_name] is None:
                    missing_by_priority[priority].append(slot_name)

        return ValidationResult(
            is_complete=len(missing_by_priority["P0"]) == 0,
            missing_slots=missing_by_priority,
            config_version=config.version
        )

    async def _get_config_with_ab_test(
        self,
        primary: str,
        secondary: str,
        user_id: str | None,
        user_profile: dict | None
    ) -> SlotPriorityConfig:
        """获取配置，支持A/B测试"""
        cache_key = f"{primary}:{secondary}"

        # 检查A/B测试分组
        if self.ab_test_service and user_id:
            experiment = await self.ab_test_service.get_active_experiment(
                "slot_priority",
                user_id
            )
            if experiment:
                cache_key = f"{cache_key}:{experiment.variant}"
                config = await self.config_source.get_config(
                    primary, secondary,
                    variant=experiment.variant
                )
                return config

        # 检查用户画像定制配置
        if user_profile and user_profile.get("vip_level"):
            vip_config = await self._get_vip_config(
                primary, secondary, user_profile
            )
            if vip_config:
                return vip_config

        # 默认配置
        if cache_key not in self._cache:
            self._cache[cache_key] = await self.config_source.get_config(
                primary, secondary
            )

        return self._cache[cache_key]

    async def _get_vip_config(
        self,
        primary: str,
        secondary: str,
        user_profile: dict
    ) -> SlotPriorityConfig | None:
        """根据用户画像获取定制配置"""
        vip_level = user_profile.get("vip_level", 0)

        # VIP用户：降低某些槽位的必填要求
        if vip_level >= 3:
            base_config = await self.config_source.get_config(primary, secondary)
            # 将部分P0槽位降级为P1（如contact_info）
            modified_slots = self._downgrade_optional_slots(base_config.slots)
            return SlotPriorityConfig(
                slots=modified_slots,
                version=f"{base_config.version}-vip{vip_level}"
            )

        return None


# 配置源实现示例
class DatabaseSlotConfigSource:
    """数据库配置源"""

    def __init__(self, db_client: DatabaseClient):
        self.db = db_client

    async def get_config(
        self,
        primary_intent: str,
        secondary_intent: str,
        variant: str | None = None
    ) -> SlotPriorityConfig:
        """从数据库加载配置"""
        query = """
            SELECT slots_config, version
            FROM slot_priority_configs
            WHERE primary_intent = $1
              AND secondary_intent = $2
              AND (variant = $3 OR variant IS NULL)
            ORDER BY variant NULLS LAST
            LIMIT 1
        """
        row = await self.db.fetchone(query, primary_intent, secondary_intent, variant)

        if row:
            return SlotPriorityConfig(
                slots=row["slots_config"],
                version=row["version"]
            )

        # 返回默认配置
        return self._get_default_config(primary_intent, secondary_intent)


class FileSlotConfigSource:
    """文件配置源（YAML/JSON）"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self._configs = self._load_configs()

    def _load_configs(self) -> dict:
        import yaml
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    async def get_config(
        self,
        primary_intent: str,
        secondary_intent: str,
        variant: str | None = None
    ) -> SlotPriorityConfig:
        key = f"{primary_intent}:{secondary_intent}"
        if variant:
            key = f"{key}:{variant}"

        config_data = self._configs.get(key, self._configs.get("default"))
        return SlotPriorityConfig(
            slots=config_data["slots"],
            version=config_data.get("version", "1.0")
        )


# 默认槽位优先级配置（作为fallback）
DEFAULT_SLOT_PRIORITIES = {
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

# 槽位优先级配置示例  # v1.1 fix: 添加完整配置示例
SLOT_PRIORITY_CONFIG = {
    "AFTER_SALES": {
        "APPLY": {
            "P0": ["order_sn", "action_type"],
            "P1": ["reason_category", "specific_item"],
            "P2": ["reason_detail", "preferred_contact"]
        },
        "CONSULT": {
            "P0": ["policy_topic"],
            "P1": ["specific_item", "order_sn"],
            "P2": []
        }
    },
    "ORDER": {
        "QUERY": {
            "P0": ["order_sn"],  # 可为"最近订单"
            "P1": ["query_type"],
            "P2": ["phone"]
        }
    },
    "PRODUCT": {
        "QUERY": {
            "P0": ["product_name"],
            "P1": ["product_id", "specification"],
            "P2": ["price_range"]
        }
    },
    # ... 其他意图组合
}
```

#### 3.2.3 TopicSwitchDetector（话题切换检测器）

**职责**：检测用户是否切换了话题

**检测策略**：
1. **显式标记检测**（高优先级）：
   - 切换关键词："换个问题"、"另外"、"对了"、"再问一下"
   - 否定语境过滤："我不想换个问题"、"先别问别的"等应排除
   - 检测规则：正则匹配显式切换词 + 否定语境排除

2. **置信度下降检测**（辅助）：
   - 当前query与上轮意图的匹配置信度 < 0.5
   - 触发重新识别

3. **意图冲突检测**：
   - 新query匹配到的意图与当前意图不兼容
   - 示例：当前在退货流程，用户突然问"优惠券怎么领"

4. **同域意图部分切换**（v1.1新增）：
   - 同一业务域内二级意图切换（如ORDER/QUERY → ORDER/CANCEL）
   - 保持已收集槽位，仅切换动作类型
   - 示例："查一下订单" → "取消这个订单"

**意图兼容性矩阵**（v1.1新增）：

```python
# 定义意图之间的兼容关系
INTENT_COMPATIBILITY = {
    # 同域兼容：相同primary_intent通常兼容
    "same_primary": "compatible",  # 可部分切换，保留槽位

    # 跨域兼容性定义
    "cross_primary": {
        # ORDER 与 LOGISTICS 高度相关，可共存
        ("ORDER", "LOGISTICS"): "compatible",
        ("LOGISTICS", "ORDER"): "compatible",

        # AFTER_SALES 与 POLICY 相关（咨询政策）
        ("AFTER_SALES", "POLICY"): "compatible",
        ("POLICY", "AFTER_SALES"): "compatible",

        # PRODUCT 与 RECOMMENDATION 相关
        ("PRODUCT", "RECOMMENDATION"): "compatible",
        ("RECOMMENDATION", "PRODUCT"): "compatible",

        # PRODUCT 与 CART 相关
        ("PRODUCT", "CART"): "compatible",
        ("CART", "PRODUCT"): "compatible",

        # 支付与订单相关
        ("PAYMENT", "ORDER"): "compatible",
        ("ORDER", "PAYMENT"): "compatible",

        # 默认不兼容
        "default": "incompatible",
    }
}


class TopicSwitchDetector:
    """话题切换检测器（v1.1增强版）"""

    # 显式切换关键词
    SWITCH_KEYWORDS = ["换个问题", "另外", "对了", "再问一下", "顺便问", "还有"]

    # 否定语境模式（排除切换）
    NEGATION_PATTERNS = [
        r"不想?换",
        r"先别问?别的",
        r"不是问",
        r"继续.*[问说]",
    ]

    def detect_switch(
        self,
        current_query: str,
        previous_intent: IntentResolutionResult | None,
        new_intent: IntentResolutionResult
    ) -> SwitchDecision:
        """
        检测话题切换

        Returns:
            SwitchDecision: 包含切换类型和策略
        """
        # 1. 否定语境检查
        if self._has_negation_context(current_query):
            return SwitchDecision(
                should_switch=False,
                switch_type=None,
                reason="negation_context_detected"
            )

        # 2. 显式切换检测
        if self._has_explicit_switch(current_query):
            return SwitchDecision(
                should_switch=True,
                switch_type="explicit",
                preserve_slots=False,
                reason="explicit_switch_keyword"
            )

        # 3. 意图兼容性检查
        if previous_intent:
            compatibility = self._check_compatibility(
                previous_intent, new_intent
            )

            if compatibility == "incompatible":
                return SwitchDecision(
                    should_switch=True,
                    switch_type="intent_conflict",
                    preserve_slots=False,
                    reason="incompatible_intents"
                )
            elif compatibility == "compatible_partial":
                # 同域切换，保留槽位
                return SwitchDecision(
                    should_switch=True,
                    switch_type="partial",
                    preserve_slots=True,
                    preserved_slots=self._determine_preserved_slots(
                        previous_intent, new_intent
                    ),
                    reason="same_domain_switch"
                )

        # 4. 置信度下降检测
        if new_intent.confidence < 0.5:
            return SwitchDecision(
                should_switch=True,
                switch_type="low_confidence",
                preserve_slots=True,
                reason="confidence_below_threshold"
            )

        return SwitchDecision(should_switch=False)

    def _has_negation_context(self, query: str) -> bool:
        """检测否定语境"""
        for pattern in self.NEGATION_PATTERNS:
            if re.search(pattern, query):
                return True
        return False

    def _determine_preserved_slots(
        self,
        previous: IntentResolutionResult,
        new_intent: IntentResolutionResult
    ) -> list[str]:
        """确定切换时应保留的槽位"""
        preserved = []

        # 订单号在ORDER/AFTER_SALES/PAYMENT域内通用
        if previous.primary_intent in ["ORDER", "AFTER_SALES", "PAYMENT"]:
            if new_intent.primary_intent in ["ORDER", "AFTER_SALES", "PAYMENT"]:
                if "order_sn" in previous.slots:
                    preserved.append("order_sn")

        # 商品ID在PRODUCT/RECOMMENDATION/CART域内通用
        if previous.primary_intent in ["PRODUCT", "RECOMMENDATION", "CART"]:
            if new_intent.primary_intent in ["PRODUCT", "RECOMMENDATION", "CART"]:
                if "product_id" in previous.slots:
                    preserved.append("product_id")

        return preserved
```

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

    # v1.1新增：用户拒绝处理
    user_refused_slots: list[str] = []  # 用户明确拒绝提供的槽位
    refused_fallback_strategy: RefusalFallbackStrategy = RefusalFallbackStrategy.SKIP


class RefusalFallbackStrategy(Enum):
    """用户拒绝提供槽位后的降级策略（v1.1新增）"""
    SKIP = "skip"                    # 跳过该槽位，继续处理
    TRANSFER_TO_HUMAN = "transfer"   # 转人工客服
    SMART_GUESS = "guess"            # 基于上下文智能猜测
    ASK_ALTERNATIVE = "alternative"  # 询问替代信息


class UserRefusalHandler:
    """用户拒绝处理器（v1.1新增）"""

    # 拒绝表达模式
    REFUSAL_PATTERNS = [
        r"不想?说",
        r"不想?告诉",
        r"不想?提供",
        r"不方便",
        r"保密",
        r"跳过",
        r"先不用",
        r"以后再说",
        r"算了",
    ]

    def detect_refusal(self, user_response: str) -> bool:
        """检测用户是否拒绝提供信息"""
        response_lower = user_response.lower()
        for pattern in self.REFUSAL_PATTERNS:
            if re.search(pattern, response_lower):
                return True
        return False

    async def handle_refusal(
        self,
        refused_slot: str,
        state: ClarificationState,
        user_profile: dict | None = None
    ) -> RefusalHandleResult:
        """
        处理用户拒绝

        策略优先级：
        1. 如果槽位是P0且无法猜测 → 转人工或询问替代
        2. 如果槽位是P1/P2 → 跳过
        3. 如果有历史数据支持 → 智能猜测
        """
        # 记录拒绝
        state.user_refused_slots.append(refused_slot)

        # 确定降级策略
        strategy = await self._determine_strategy(refused_slot, state, user_profile)

        if strategy == RefusalFallbackStrategy.SKIP:
            return RefusalHandleResult(
                action="skip_slot",
                message=None,
                continue_clarification=True
            )

        elif strategy == RefusalFallbackStrategy.TRANSFER_TO_HUMAN:
            return RefusalHandleResult(
                action="transfer_to_human",
                message="理解您的顾虑，我为您转接人工客服协助处理。",
                continue_clarification=False
            )

        elif strategy == RefusalFallbackStrategy.SMART_GUESS:
            guessed_value = await self._smart_guess(refused_slot, state)
            if guessed_value:
                return RefusalHandleResult(
                    action="smart_guess",
                    message=f"根据您的历史记录，订单可能是{guessed_value}，对吗？",
                    guessed_value=guessed_value,
                    continue_clarification=True
                )
            else:
                # 无法猜测，降级为询问替代
                return await self._ask_alternative(refused_slot, state)

        elif strategy == RefusalFallbackStrategy.ASK_ALTERNATIVE:
            return await self._ask_alternative(refused_slot, state)

        return RefusalHandleResult(action="skip_slot", continue_clarification=True)

    async def _determine_strategy(
        self,
        slot: str,
        state: ClarificationState,
        user_profile: dict | None
    ) -> RefusalFallbackStrategy:
        """确定降级策略"""
        # 获取槽位优先级
        priority = self._get_slot_priority(slot, state.current_intent)

        # P0槽位必须处理
        if priority == "P0":
            # 检查是否可以智能猜测
            if await self._can_smart_guess(slot, state):
                return RefusalFallbackStrategy.SMART_GUESS
            # VIP用户转人工
            if user_profile and user_profile.get("vip_level", 0) >= 2:
                return RefusalFallbackStrategy.TRANSFER_TO_HUMAN
            # 询问替代信息
            return RefusalFallbackStrategy.ASK_ALTERNATIVE

        # P1/P2槽位可跳过
        return RefusalFallbackStrategy.SKIP

    async def _smart_guess(
        self,
        slot: str,
        state: ClarificationState
    ) -> str | None:
        """基于上下文智能猜测槽位值"""
        if slot == "order_sn":
            # 从最近订单中猜测
            recent_orders = await self._get_recent_orders(state.session_id)
            if recent_orders:
                return recent_orders[0]["order_sn"]

        elif slot == "reason_category":
            # 基于商品类别和历史退货记录猜测
            product_category = state.collected_slots.get("product_category")
            if product_category:
                return self._guess_reason_by_category(product_category)

        return None

    async def _ask_alternative(
        self,
        slot: str,
        state: ClarificationState
    ) -> RefusalHandleResult:
        """询问替代信息"""
        alternatives = {
            "order_sn": "您可以提供下单时使用的手机号，我帮您查找",
            "phone": "您可以提供订单号，我通过订单号查询",
            "reason_detail": "您可以选择一个最接近的选项，或者简单描述一下",
        }

        message = alternatives.get(
            slot,
            "那您能提供其他相关信息吗？"
        )

        return RefusalHandleResult(
            action="ask_alternative",
            message=message,
            continue_clarification=True
        )
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
                        "PROMOTION", "PAYMENT", "LOGISTICS", "PRODUCT",
                        "RECOMMENDATION", "CART", "COMPLAINT", "OTHER"],
                "description": "一级意图：业务域"
            },
            "secondary_intent": {
                "type": "string",
                "enum": ["QUERY", "APPLY", "MODIFY", "CANCEL", "CONSULT",
                        "ADD", "REMOVE", "COMPARE"],
                "description": "二级意图：动作类型"
            },
            "tertiary_intent": {
                "type": "string",
                "description": "三级意图：具体子意图（如有），必须来自TERTIARY_INTENT_CONFIG中定义的有效值"
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
                    "product_id": {"type": "string"},
                    "product_name": {"type": "string"},
                    "category": {"type": "string"},
                    "cart_item_id": {"type": "string"},
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

# v1.1新增：三级意图约束配置表
TERTIARY_INTENT_CONFIG: dict[tuple[str, str], list[str]] = {
    # AFTER_SALES 场景
    ("AFTER_SALES", "CONSULT"): [
        "REFUND_SHIPPING_FEE",
        "REFUND_TIMELINE",
        "EXCHANGE_SIZE",
    ],
    ("AFTER_SALES", "APPLY"): [
        "REFUND_QUALITY_ISSUE",
        "REFUND_SIZE_ISSUE",
        "REFUND_NOT_AS_DESCRIBED",
    ],

    # ORDER 场景
    ("ORDER", "QUERY"): [
        "ORDER_TRACKING_DETAIL",
        "ORDER_STATUS_ESTIMATE",
    ],

    # POLICY 场景
    ("POLICY", "CONSULT"): [
        "POLICY_RETURN_EXCEPTION",
        "POLICY_SHIPPING_FEE",
    ],

    # PRODUCT 场景（v1.1新增）
    ("PRODUCT", "QUERY"): [
        "PRODUCT_STOCK",
        "PRODUCT_SPEC",
        "PRODUCT_DETAIL",
        "PRODUCT_REVIEW",
    ],
    ("PRODUCT", "COMPARE"): [
        "PRODUCT_PRICE_COMPARE",
        "PRODUCT_SPEC_COMPARE",
    ],

    # RECOMMENDATION 场景（v1.1新增）
    ("RECOMMENDATION", "QUERY"): [
        "RECOMMEND_SIMILAR",
        "RECOMMEND_COMPLEMENTARY",
        "RECOMMEND_PERSONALIZED",
        "RECOMMEND_TRENDING",
    ],

    # CART 场景（v1.1新增）
    ("CART", "QUERY"): [
        "CART_VIEW",
    ],
    ("CART", "ADD"): [
        "CART_UPDATE_QUANTITY",
    ],
    ("CART", "REMOVE"): {
        "tertiary_intents": ["CART_REMOVE_ITEM", "CART_CLEAR_ALL"],  # v1.1 fix: CART_REMOVE_ITEM表示选择并移除特定商品
        "description": "从购物车移除商品"
    },
    ("CART", "MODIFY"): [
        "CART_UPDATE_QUANTITY",
        "CART_REMOVE_ITEM",  # v1.1 fix: 统一命名
    ],
    ("CART", "APPLY"): [
        "CART_CHECKOUT",
    ],
}


def validate_tertiary_intent(primary: str, secondary: str, tertiary: str | None) -> bool:
    """验证三级意图是否有效（v1.1新增）"""
    if tertiary is None:
        return True

    valid_tertiary = TERTIARY_INTENT_CONFIG.get((primary, secondary), [])
    return tertiary in valid_tertiary
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

**多意图处理详细实现**（v1.1新增）：

```python
class MultiIntentProcessor:
    """多意图处理器"""

    # 多意图分隔符模式
    SPLIT_PATTERNS = [
        r"[，,]\s*顺便",
        r"[，,]\s*还有",
        r"[，,]\s*另外",
        r"[；;]",
        r"[。\.]",
    ]

    async def process(
        self,
        query: str,
        session_id: str,
        conversation_history: list[dict] | None = None
    ) -> MultiIntentResult:
        """
        处理多意图输入

        流程：
        1. 检测是否为多意图
        2. 拆分意图
        3. 槽位共享
        4. 优先级排序
        5. 执行并处理回滚
        """
        # Step 1: 检测多意图
        is_multi = self._detect_multi_intent(query)

        if not is_multi:
            # 单意图，直接处理
            intent = await self.intent_classifier.classify(query)
            return MultiIntentResult(intents=[intent])

        # Step 2: 拆分意图
        sub_queries = self._split_query(query)

        # Step 3: 分别识别每个子意图
        intents = []
        for sub_query in sub_queries:
            intent = await self.intent_classifier.classify(sub_query)
            intents.append(intent)

        # Step 4: 槽位共享机制
        shared_slots = self._extract_shared_slots(intents)
        intents = self._propagate_shared_slots(intents, shared_slots)

        # Step 5: 优先级排序
        sorted_intents = self._sort_by_priority(intents)

        # Step 6: 执行多意图
        execution_result = await self._execute_intents(
            sorted_intents, session_id
        )

        return MultiIntentResult(
            intents=sorted_intents,
            execution_result=execution_result,
            shared_slots=shared_slots
        )

    def _detect_multi_intent(self, query: str) -> bool:
        """检测是否为多意图输入"""
        # 基于分隔符检测
        for pattern in self.SPLIT_PATTERNS:
            if re.search(pattern, query):
                return True

        # 基于置信度分布检测（备选）
        # 如果多个意图的置信度都较高，可能是多意图
        return False

    def _split_query(self, query: str) -> list[str]:
        """基于分隔符拆分查询"""
        # 先尝试LLM辅助拆分
        split_result = self._llm_assisted_split(query)

        if split_result and len(split_result) > 1:
            return split_result

        # 回退到规则拆分
        for pattern in self.SPLIT_PATTERNS:
            parts = re.split(pattern, query)
            if len(parts) > 1:
                return [p.strip() for p in parts if p.strip()]

        return [query]

    def _llm_assisted_split(self, query: str) -> list[str] | None:
        """LLM辅助拆分多意图"""
        prompt = f"""
        分析以下用户输入，如果包含多个独立意图，请拆分为多个句子。
        每个句子应该表达一个完整的意图。

        用户输入: {query}

        输出JSON格式: {{"intents": ["意图1", "意图2", ...]}}
        如果是单意图，输出: {{"intents": ["{query}"]}}
        """

        try:
            response = self.llm_client.complete(prompt=prompt, temperature=0.1)
            result = json.loads(response)
            return result.get("intents")
        except Exception:
            return None

    def _extract_shared_slots(
        self,
        intents: list[IntentResolutionResult]
    ) -> dict[str, Any]:
        """
        提取可共享的槽位

        共享规则：
        - order_sn: 在ORDER/AFTER_SALES/PAYMENT/LOGISTICS间共享
        - product_id: 在PRODUCT/RECOMMENDATION/CART间共享
        - user_id: 全局共享
        """
        shared = {}

        # 收集所有槽位
        all_slots = {}
        for intent in intents:
            for slot_name, value in intent.slots.items():
                if slot_name not in all_slots:
                    all_slots[slot_name] = []
                all_slots[slot_name].append((intent.primary_intent, value))

        # 识别可共享槽位
        for slot_name, occurrences in all_slots.items():
            if len(occurrences) > 1:  # 多个意图都有这个槽位
                # 检查意图间兼容性
                primary_intents = {occ[0] for occ in occurrences}
                if self._are_intents_compatible_for_sharing(
                    slot_name, primary_intents
                ):
                    # 使用第一个非空值作为共享值
                    shared[slot_name] = occurrences[0][1]

        return shared

    def _propagate_shared_slots(
        self,
        intents: list[IntentResolutionResult],
        shared_slots: dict[str, Any]
    ) -> list[IntentResolutionResult]:
        """将共享槽位传播到所有兼容的意图"""
        for intent in intents:
            for slot_name, value in shared_slots.items():
                if slot_name not in intent.slots:
                    # 检查该槽位是否适用于此意图
                    if self._is_slot_applicable(slot_name, intent):
                        intent.slots[slot_name] = value

        return intents

    def _sort_by_priority(
        self,
        intents: list[IntentResolutionResult]
    ) -> list[IntentResolutionResult]:
        """
        按优先级排序意图

        排序规则：
        1. 查询类优先于申请类（QUERY > CONSULT > others）
        2. 当前流程中的意图优先
        3. 依赖关系：被依赖的意图先执行
        """
        priority_map = {
            "QUERY": 1,
            "CONSULT": 2,
            "CANCEL": 3,
            "MODIFY": 4,
            "APPLY": 5,
            "ADD": 6,
            "REMOVE": 7,
        }

        def get_priority(intent: IntentResolutionResult) -> int:
            return priority_map.get(intent.secondary_intent, 10)

        return sorted(intents, key=get_priority)

    async def _execute_intents(
        self,
        intents: list[IntentResolutionResult],
        session_id: str
    ) -> IntentExecutionResult:
        """
        依次执行多个意图，支持回滚
        """
        executed = []
        failed_intent = None
        rollback_performed = False

        for idx, intent in enumerate(intents):
            try:
                result = await self._execute_single_intent(intent, session_id)
                executed.append({
                    "intent": intent,
                    "result": result,
                    "status": "success"
                })
            except Exception as e:
                failed_intent = {
                    "intent": intent,
                    "error": str(e),
                    "index": idx
                }

                # 执行回滚
                rollback_result = await self._rollback_executed(
                    executed, session_id
                )
                rollback_performed = True

                return IntentExecutionResult(
                    status="failed",
                    executed=executed,
                    failed=failed_intent,
                    rollback_performed=rollback_performed,
                    rollback_result=rollback_result
                )

        return IntentExecutionResult(
            status="success",
            executed=executed,
            failed=None,
            rollback_performed=False
        )

    async def _rollback_executed(
        self,
        executed: list[dict],
        session_id: str
    ) -> RollbackResult:
        """
        回滚已执行的意图

        回滚策略：
        1. 按相反顺序回滚
        2. 只回滚可逆操作（如ADD→REMOVE）
        3. 记录回滚日志
        """
        rollback_log = []

        for executed_item in reversed(executed):
            intent = executed_item["intent"]
            result = executed_item["result"]

            # 检查是否可回滚
            if self._is_rollbackable(intent):
                rollback_action = await self._perform_rollback(
                    intent, result, session_id
                )
                rollback_log.append({
                    "intent": intent,
                    "rollback_action": rollback_action
                })
            else:
                rollback_log.append({
                    "intent": intent,
                    "rollback_action": "not_rollbackable"
                })

        return RollbackResult(log=rollback_log)

    def _is_rollbackable(self, intent: IntentResolutionResult) -> bool:
        """检查意图是否可回滚"""
        # 查询类操作无需回滚
        if intent.secondary_intent == "QUERY":
            return False

        # ADD操作可回滚（REMOVE）
        # MODIFY操作可回滚（反向修改）
        # APPLY操作通常不可回滚
        return intent.secondary_intent in ["ADD", "MODIFY", "CANCEL"]
```

---

## 6. 边界情况处理

### 6.1 情况对照表

| 情况 | 检测条件 | 处理策略 | 示例 |
|------|---------|---------|------|
| **无法识别** | confidence < 0.3 | 礼貌回复+建议可咨询范围 | "我不太理解，您可以问订单、退货或政策相关问题" |
| **意图冲突** | 多个意图置信度差<0.2 | 主动让用户选择 | "您是要查询订单，还是申请退货？" |
| **敏感内容** | 命中安全关键词或LLM语义检测 | 触发安全过滤，礼貌结束 | "抱歉，我无法回答这个问题" |
| **重复追问** | 同一槽位追问>2次 | 提供跳过/转人工选项 | "您可以跳过此问题，或转接人工客服" |
| **槽位无效** | 用户提供值格式错误 | 提示正确格式，重新询问 | "订单号格式应为SN开头，请重新提供" |
| **意图漂移** | 中间轮次突然切换 | 确认是否切换，保存原状态 | "是否改为咨询退货政策？之前的退货申请将暂存" |
| **过度澄清** | 澄清轮次>=3 | 转人工或智能猜测 | "我将根据已有信息为您处理..." |
| **同域切换** | 同一primary_intent，不同secondary（v1.1新增） | 保留槽位，切换动作 | "查订单"→"取消订单"，保留order_sn |
| **否定语境** | 用户拒绝切换话题（v1.1新增） | 继续原话题，忽略新意图 | "我不想换个问题"→继续原流程 |
| **兼容意图** | 意图兼容但不同域（v1.1新增） | 允许共存，顺序处理 | 先查订单，再问物流 |

**话题切换详细处理策略**（v1.1新增）：

```python
class TopicSwitchHandler:
    """话题切换处理器"""

    async def handle_switch(
        self,
        decision: SwitchDecision,
        current_state: ConversationState,
        new_intent: IntentResolutionResult
    ) -> HandlerResult:
        """处理话题切换"""

        if not decision.should_switch:
            # 不切换，继续当前话题
            return HandlerResult(action="continue_current")

        if decision.switch_type == "explicit":
            # 显式切换：保存当前状态，开始新话题
            await self._save_suspended_state(current_state)
            return HandlerResult(
                action="switch_new",
                message="好的，我们来处理新问题。",
                new_intent=new_intent
            )

        elif decision.switch_type == "partial":
            # 同域部分切换：保留槽位，切换意图
            preserved_slots = {
                k: v for k, v in current_state.slots.items()
                if k in decision.preserved_slots
            }
            new_intent.slots.update(preserved_slots)

            return HandlerResult(
                action="partial_switch",
                message=None,  # 无需特别说明，自然过渡
                new_intent=new_intent,
                preserved_slots=decision.preserved_slots
            )

        elif decision.switch_type == "intent_conflict":
            # 意图冲突：询问用户是否切换
            return HandlerResult(
                action="confirm_switch",
                message=f"您是要咨询{new_intent.primary_intent}相关问题吗？"
                        f"当前{current_state.current_intent.primary_intent}问题将暂存。",
                requires_confirmation=True
            )

        elif decision.switch_type == "low_confidence":
            # 低置信度：尝试澄清
            return HandlerResult(
                action="clarify",
                message="请问您是想咨询当前订单问题，还是有其他问题？"
            )

        return HandlerResult(action="continue_current")
```

### 6.2 安全过滤架构（v1.1增强版）  # v1.1 fix: 重构章节结构，拆分为更清晰的子结构

#### 6.2.1 整体架构

```python
class SafetyFilter:
    """安全过滤器 - 多层防护"""

    def __init__(self):
        self.keyword_filter = KeywordFilter()
        self.llm_semantic_filter = LLMSemanticFilter()
        self.prompt_injection_detector = PromptInjectionDetector()
        self.ecommerce_special_filter = EcommerceSpecialFilter()

    async def check(self, query: str, context: dict | None = None) -> SafetyCheckResult:
        """
        执行安全过滤检查

        检查顺序（由轻到重）：
        1. 输入长度限制
        2. 关键词过滤
        3. Prompt注入检测
        4. 电商特殊场景过滤
        5. LLM语义安全检测
        """
        # 1. 输入长度限制
        if len(query) > 2000:  # max_tokens约2000
            return SafetyCheckResult(
                is_safe=False,
                violation_type="input_too_long",
                action="block",
                response="输入内容过长，请简要描述您的问题。"
            )

        # 2. Prompt注入检测
        injection_result = self.prompt_injection_detector.detect(query)
        if injection_result.is_injection:
            return SafetyCheckResult(
                is_safe=False,
                violation_type="prompt_injection",
                action="block_and_log",
                response="抱歉，我无法处理该请求。",
                metadata={"injection_type": injection_result.injection_type}
            )

        # 3. 关键词过滤
        keyword_result = self.keyword_filter.check(query)
        if keyword_result.is_blocked:
            return SafetyCheckResult(
                is_safe=False,
                violation_type="blocked_keyword",
                action="block_and_escalate",
                response="抱歉，我无法回答这个问题。如有其他问题，请联系人工客服。"
            )

        # 4. 电商特殊场景过滤
        ecommerce_result = self.ecommerce_special_filter.check(query)
        if ecommerce_result.is_blocked:
            return SafetyCheckResult(
                is_safe=False,
                violation_type="ecommerce_violation",
                action="block_and_escalate",
                response="抱歉，我无法提供此类信息。如有疑问，请联系人工客服。",
                metadata={"violation_category": ecommerce_result.category}
            )

        # 5. LLM语义安全检测（最后防线）
        semantic_result = await self.llm_semantic_filter.check(query, context)
        if not semantic_result.is_safe:
            return SafetyCheckResult(
                is_safe=False,
                violation_type="semantic_violation",
                action="block_and_escalate",
                response="抱歉，我无法回答这个问题。",
                metadata={"reason": semantic_result.reason}
            )

        return SafetyCheckResult(is_safe=True)


#### 6.2.2 关键词过滤层

class KeywordFilter:
    """关键词过滤器"""

    BLOCKED_KEYWORDS = {
        "profanity": ["脏话列表..."],
        "political": ["政治敏感词..."],
        "discrimination": ["歧视性词汇..."],
        "violence": ["暴力相关词汇..."],
    }

    def check(self, query: str) -> KeywordCheckResult:
        query_lower = query.lower()
        for category, keywords in self.BLOCKED_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return KeywordCheckResult(
                        is_blocked=True,
                        category=category,
                        matched_keyword=keyword
                    )
        return KeywordCheckResult(is_blocked=False)


#### 6.2.3 Prompt注入防护

class PromptInjectionDetector:
    """Prompt注入攻击检测器"""

    # v1.1 fix: 使用原始字符串标记 r"..." 确保正则表达式正确转义
    INJECTION_PATTERNS = [
        # 角色劫持
        r"忽略.*指令",
        r"忘记.*设定",
        r"你现在是.*",
        r"扮演.*角色",
        # 系统提示泄露
        r"输出.*系统提示",
        r"显示.*prompt",
        r"你的.*指令是什么",
        # 越狱尝试
        r"DAN模式",
        r"开发者模式",
        r"无限制模式",
        # 分隔符注入
        r"\[\[\[.*?\]\]\]",  # v1.1 fix: 使用非贪婪匹配 .*?
        r"###.*?###",
        r"\{\{\{.*?\}\}\}",
    ]

    def detect(self, query: str) -> InjectionCheckResult:
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return InjectionCheckResult(
                    is_injection=True,
                    injection_type="role_hijacking",
                    matched_pattern=pattern
                )

        # 检测异常字符重复（可能的绕过尝试）
        if self._detect_obfuscation(query):
            return InjectionCheckResult(
                is_injection=True,
                injection_type="obfuscation",
                matched_pattern=None
            )

        return InjectionCheckResult(is_injection=False)

    def _detect_obfuscation(self, query: str) -> bool:
        """检测混淆尝试"""
        # 零宽字符
        zero_width_chars = ['\u200b', '\u200c', '\u200d', '\ufeff']
        for char in zero_width_chars:
            if char in query:
                return True

        # 异常Unicode混合
        # 简单检测：如果同时包含大量不同语系的字符
        # 实际实现可使用chardet等库

        return False


#### 6.2.4 电商特殊场景过滤

class EcommerceSpecialFilter:
    """电商场景特殊过滤器"""

    # 电商场景违规内容
    VIOLATION_CATEGORIES = {
        "fake_order": [
            r"刷单",
            r"刷销量",
            r"虚假交易",
            r"提升.*销量",
        ],
        "malicious_refund": [
            r"恶意退款.*教程",
            r"退款.*攻略.*不退货",
            r"白嫖.*教程",
            r"仅退款.*技巧",
        ],
        "fake_review": [
            r"刷好评",
            r"删差评.*教程",
            r"修改.*评价.*方法",
        ],
        "account_fraud": [
            r"盗号",
            r"破解.*账号",
            r"绕过.*实名",
        ],
        "price_manipulation": [
            r"改价.*漏洞",
            r"价格.*破解",
            r"优惠券.*套现",
        ],
    }

    def check(self, query: str) -> EcommerceCheckResult:
        query_lower = query.lower()

        for category, patterns in self.VIOLATION_CATEGORIES.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return EcommerceCheckResult(
                        is_blocked=True,
                        category=category,
                        matched_pattern=pattern
                    )

        return EcommerceCheckResult(is_blocked=False)


#### 6.2.5 LLM语义安全检测

class LLMSemanticFilter:
    """LLM语义安全检测层"""

    SAFETY_CHECK_PROMPT = """
    你是一个内容安全审核助手。请分析以下用户输入，判断是否存在以下问题：

    1. 有害内容：暴力、仇恨、歧视、色情
    2. 违法内容：诈骗、毒品、赌博、侵权
    3. 平台滥用：试图操纵系统、获取未授权信息
    4. 社交工程：试图获取他人隐私信息

    用户输入: {query}

    请输出JSON格式结果：
    {{
        "is_safe": true/false,
        "violation_type": "类型或null",
        "confidence": 0-1,
        "reason": "判断理由"
    }}
    """

    async def check(self, query: str, context: dict | None) -> SemanticCheckResult:
        """使用LLM进行语义安全检测"""
        prompt = self.SAFETY_CHECK_PROMPT.format(query=query)

        # 调用LLM进行判断
        response = await self.llm_client.complete(
            prompt=prompt,
            temperature=0.1,
            max_tokens=200
        )

        try:
            result = json.loads(response)
            return SemanticCheckResult(
                is_safe=result.get("is_safe", True),
                violation_type=result.get("violation_type"),
                confidence=result.get("confidence", 1.0),
                reason=result.get("reason")
            )
        except json.JSONDecodeError:
            # 解析失败，保守处理（允许通过但记录日志）
            return SemanticCheckResult(is_safe=True)


#### 6.2.6 安全过滤配置示例

# 安全过滤配置
SAFETY_CONFIG = {
    "max_input_length": 2000,
    "max_tokens": 2000,
    "enable_llm_semantic_check": True,
    "llm_check_threshold": 0.7,  # 置信度阈值
    "block_action": "block_and_escalate",  # 或仅 "block"
    "escalation_channels": ["security_team", "admin"],
}
```

---

## 7. 提示词设计

### 7.1 System Prompt（精简版）

```
你是电商客服意图识别专家。分析用户输入，识别其真实意图。

## 意图层级
一级（业务域）：ORDER(订单), AFTER_SALES(售后), POLICY(政策), ACCOUNT(账户), PROMOTION(优惠), PAYMENT(支付), LOGISTICS(物流), PRODUCT(商品), RECOMMENDATION(推荐), CART(购物车), COMPLAINT(投诉), OTHER(其他)
二级（动作）：QUERY(查询), APPLY(申请), MODIFY(修改), CANCEL(取消), CONSULT(咨询), ADD(添加), REMOVE(移除), COMPARE(比较)
三级（子意图）：根据上下文判断，如REFUND_SHIPPING_FEE(退货运费), REFUND_TIMELINE(退款时效), PRODUCT_STOCK(商品库存), RECOMMEND_SIMILAR(相似推荐)等

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

### 9.3 自动化评估Pipeline设计（v1.1新增）

```python
class IntentEvaluationPipeline:
    """意图识别自动化评估Pipeline"""

    def __init__(
        self,
        intent_service: IntentRecognitionService,
        golden_dataset: GoldenDataset,
        metrics_calculator: MetricsCalculator
    ):
        self.intent_service = intent_service
        self.golden_dataset = golden_dataset
        self.metrics = metrics_calculator

    async def run_evaluation(
        self,
        test_suite: str | None = None,
        tags: list[str] | None = None
    ) -> EvaluationReport:
        """
        运行评估

        Args:
            test_suite: 指定测试集名称，None则运行全部
            tags: 按标签过滤测试用例
        """
        # 加载测试用例
        test_cases = await self.golden_dataset.load_cases(
            test_suite=test_suite,
            tags=tags
        )

        results = []
        for case in test_cases:
            # 执行意图识别
            prediction = await self.intent_service.recognize(
                query=case.input,
                session_id=f"test_{case.id}"
            )

            # 对比预期结果
            result = self._compare_result(case.expected, prediction)
            results.append(result)

        # 计算指标
        metrics = self.metrics.calculate(results)

        return EvaluationReport(
            metrics=metrics,
            details=results,
            timestamp=datetime.now()
        )

    def _compare_result(
        self,
        expected: dict,
        prediction: IntentResolutionResult
    ) -> ComparisonResult:
        """对比预期和实际结果"""
        return ComparisonResult(
            primary_correct=expected["primary"] == prediction.primary_intent,
            secondary_correct=expected["secondary"] == prediction.secondary_intent,
            tertiary_correct=expected.get("tertiary") == prediction.tertiary_intent,
            slots_match=self._compare_slots(
                expected.get("slots", {}),
                prediction.slots
            ),
            confidence_pass=prediction.confidence >= expected.get("min_confidence", 0.7)
        )


class GoldenDataset:
    """黄金数据集管理（v1.1新增）"""

    def __init__(self, storage: DatasetStorage):
        self.storage = storage

    async def load_cases(
        self,
        test_suite: str | None = None,
        tags: list[str] | None = None
    ) -> list[TestCase]:
        """加载测试用例"""
        query = "SELECT * FROM test_cases WHERE 1=1"
        params = []

        if test_suite:
            query += " AND test_suite = ?"
            params.append(test_suite)

        if tags:
            query += " AND tags && ?"
            params.append(tags)

        query += " AND is_active = true ORDER BY priority DESC"

        rows = await self.storage.fetchall(query, params)
        return [TestCase.from_row(row) for row in rows]

    async def add_case(
        self,
        test_case: TestCase,
        verified_by: str | None = None
    ) -> None:
        """添加新的测试用例"""
        test_case.verified_by = verified_by
        test_case.created_at = datetime.now()
        await self.storage.insert(test_case)

    async def update_case(
        self,
        case_id: str,
        updates: dict
    ) -> None:
        """更新测试用例"""
        updates["updated_at"] = datetime.now()
        await self.storage.update(case_id, updates)

    async def get_case_stats(self) -> DatasetStats:
        """获取数据集统计"""
        stats = await self.storage.fetchone("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN is_verified THEN 1 END) as verified,
                COUNT(DISTINCT test_suite) as suites,
                COUNT(DISTINCT unnest(tags)) as tag_count
            FROM test_cases
            WHERE is_active = true
        """)
        return DatasetStats(**stats)


class RegressionTester:
    """回归测试机制（v1.1新增）"""

    def __init__(self, pipeline: IntentEvaluationPipeline):
        self.pipeline = pipeline
        self.baseline_results: dict[str, EvaluationReport] = {}

    async def establish_baseline(
        self,
        version: str,
        test_suite: str = "regression"
    ) -> None:
        """建立基线结果"""
        report = await self.pipeline.run_evaluation(test_suite=test_suite)
        self.baseline_results[version] = report

        # 保存基线
        await self._save_baseline(version, report)

    async def run_regression_test(
        self,
        current_version: str,
        baseline_version: str
    ) -> RegressionReport:
        """运行回归测试"""
        # 加载基线
        baseline = self.baseline_results.get(baseline_version)
        if not baseline:
            baseline = await self._load_baseline(baseline_version)

        # 运行当前版本测试
        current = await self.pipeline.run_evaluation(test_suite="regression")

        # 对比差异
        diff = self._compare_reports(baseline, current)

        return RegressionReport(
            baseline_version=baseline_version,
            current_version=current_version,
            metrics_diff=diff,
            regressions=self._identify_regressions(diff),
            improvements=self._identify_improvements(diff)
        )

    def _compare_reports(
        self,
        baseline: EvaluationReport,
        current: EvaluationReport
    ) -> MetricsDiff:
        """对比两个报告的差异"""
        return MetricsDiff(
            primary_accuracy_delta=
                current.metrics.primary_accuracy - baseline.metrics.primary_accuracy,
            secondary_accuracy_delta=
                current.metrics.secondary_accuracy - baseline.metrics.secondary_accuracy,
            slot_f1_delta=
                current.metrics.slot_f1 - baseline.metrics.slot_f1,
        )


class OnlineABTest:
    """在线A/B测试方案（v1.1新增）"""

    def __init__(
        self,
        variant_a: IntentRecognitionService,
        variant_b: IntentRecognitionService,
        assignment_service: UserAssignmentService
    ):
        self.variant_a = variant_a  # 对照组
        self.variant_b = variant_b  # 实验组
        self.assignment = assignment_service

    async def route_request(
        self,
        user_id: str,
        query: str,
        session_id: str
    ) -> IntentRecognitionResult:
        """根据分组路由到不同版本"""
        variant = await self.assignment.get_variant(user_id, "intent_recognition_v2")

        if variant == "A":
            result = await self.variant_a.recognize(query, session_id)
            result.variant = "A"
        else:
            result = await self.variant_b.recognize(query, session_id)
            result.variant = "B"

        # 记录日志用于后续分析
        await self._log_exposure(user_id, variant, query, result)

        return result

    async def analyze_results(
        self,
        experiment_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> ABTestReport:
        """分析A/B测试结果"""
        # 获取实验数据
        data = await self._fetch_experiment_data(experiment_id, start_time, end_time)

        # 计算关键指标
        metrics = {
            "primary_accuracy": self._calculate_accuracy(data, "primary"),
            "clarification_rate": self._calculate_clarification_rate(data),
            "user_satisfaction": self._calculate_satisfaction(data),
            "avg_response_time": self._calculate_latency(data),
        }

        # 统计显著性检验
        significance = self._statistical_test(data)

        return ABTestReport(
            experiment_id=experiment_id,
            metrics=metrics,
            significance=significance,
            recommendation=self._generate_recommendation(metrics, significance)
        )


# 测试配置（v1.1新增）
TEST_CONFIG = {
    "golden_dataset": {
        "min_verified_cases": 1000,
        "coverage_requirements": {
            "primary_intents": 0.95,  # 95%的一级意图覆盖率
            "secondary_intents": 0.90,
            "edge_cases": 0.80,
        }
    },
    "regression_thresholds": {
        "primary_accuracy": 0.95,
        "secondary_accuracy": 0.92,
        "slot_f1": 0.88,
        "max_regression": 0.02,  # 最大允许回退2%
    },
    "ab_test": {
        "min_sample_size": 10000,
        "confidence_level": 0.95,
        "ramp_up_percentage": [5, 10, 25, 50, 100],  # 逐步放量
    }
}
```

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

## 12. 数据隐私与安全（v1.1新增）

### 12.1 槽位数据脱敏规则

```python
class DataMaskingRules:
    """数据脱敏规则（v1.1新增）"""

    # 敏感槽位定义
    SENSITIVE_SLOTS = {
        "order_sn": {"level": "medium", "retention_days": 365},
        "phone": {"level": "high", "retention_days": 180},
        "email": {"level": "high", "retention_days": 180},
        "id_card": {"level": "critical", "retention_days": 90},
        "address": {"level": "high", "retention_days": 180},
        "payment_info": {"level": "critical", "retention_days": 30},
    }

    @staticmethod
    def mask_order_sn(order_sn: str, visible_prefix: int = 4) -> str:
        """订单号脱敏：SN12345678 → SN12****78"""
        if len(order_sn) <= visible_prefix + 2:
            return order_sn[:visible_prefix] + "****"
        return order_sn[:visible_prefix] + "****" + order_sn[-2:]

    @staticmethod
    def mask_phone(phone: str) -> str:
        """手机号脱敏：13812345678 → 138****5678"""
        if len(phone) != 11:
            return phone[:3] + "****" + phone[-4:] if len(phone) > 7 else "****"
        return phone[:3] + "****" + phone[-4:]

    @staticmethod
    def mask_email(email: str) -> str:
        """邮箱脱敏：user@example.com → u***@example.com"""
        parts = email.split("@")
        if len(parts) != 2:
            return "***"
        local = parts[0]
        domain = parts[1]
        masked_local = local[0] + "***" if len(local) > 1 else "***"
        return f"{masked_local}@{domain}"

    @staticmethod
    def mask_address(address: str, visible_chars: int = 6) -> str:
        """地址脱敏：保留省市区，详细地址脱敏"""
        # 简单实现：保留前N个字符
        if len(address) <= visible_chars:
            return address
        return address[:visible_chars] + "***"


class SensitiveDataHandler:
    """敏感数据处理器（v1.1新增）"""

    def __init__(self, masking_rules: DataMaskingRules):
        self.masking_rules = masking_rules

    def mask_slots_for_logging(
        self,
        slots: dict[str, Any]
    ) -> dict[str, Any]:
        """
        对槽位数据进行脱敏，用于日志记录
        """
        masked = {}
        for slot_name, value in slots.items():
            if slot_name in self.masking_rules.SENSITIVE_SLOTS:
                mask_func = getattr(
                    self.masking_rules,
                    f"mask_{slot_name}",
                    lambda x: "***"
                )
                masked[slot_name] = mask_func(str(value))
            else:
                masked[slot_name] = value
        return masked

    def mask_slots_for_display(
        self,
        slots: dict[str, Any]
    ) -> dict[str, Any]:
        """
        对槽位数据进行脱敏，用于前端展示
        """
        # 展示用脱敏可能更严格
        return self.mask_slots_for_logging(slots)
```

### 12.2 数据存储与传输安全

```python
class DataSecurityConfig:
    """数据安全配置（v1.1新增）"""

    # 传输安全
    TRANSPORT = {
        "enforce_tls": True,
        "min_tls_version": "1.2",
        "certificate_pinning": True,
    }

    # 存储安全
    STORAGE = {
        "encryption_at_rest": True,
        "encryption_algorithm": "AES-256-GCM",
        "key_rotation_days": 90,
    }

    # 访问控制
    ACCESS_CONTROL = {
        "role_based_access": True,
        "principle_of_least_privilege": True,
        "audit_logging": True,
    }


class SecureSlotStorage:
    """安全槽位存储（v1.1新增）"""

    def __init__(
        self,
        encryption_service: EncryptionService,
        access_logger: AuditLogger
    ):
        self.encryption = encryption_service
        self.logger = access_logger

    async def store_slots(
        self,
        session_id: str,
        slots: dict[str, Any],
        user_id: str
    ) -> None:
        """安全存储槽位数据"""
        # 1. 识别敏感数据
        sensitive_slots = {
            k: v for k, v in slots.items()
            if k in DataMaskingRules.SENSITIVE_SLOTS
        }

        # 2. 加密敏感数据
        encrypted_slots = {}
        for slot_name, value in sensitive_slots.items():
            encrypted_slots[slot_name] = await self.encryption.encrypt(
                value=str(value),
                context={"session_id": session_id, "slot_name": slot_name}
            )

        # 3. 存储（敏感数据加密，非敏感数据明文）
        storage_data = {
            "session_id": session_id,
            "user_id": user_id,
            "slots": {k: v for k, v in slots.items() if k not in sensitive_slots},
            "encrypted_slots": encrypted_slots,
            "created_at": datetime.now(),
        }

        await self._save_to_storage(storage_data)

        # 4. 记录审计日志
        self.logger.log(
            action="slot_storage",
            user_id=user_id,
            session_id=session_id,
            sensitive_fields=list(sensitive_slots.keys())
        )

    async def retrieve_slots(
        self,
        session_id: str,
        requesting_user: str
    ) -> dict[str, Any] | None:
        """检索槽位数据（带权限检查）"""
        # 1. 从存储加载
        data = await self._load_from_storage(session_id)
        if not data:
            return None

        # 2. 权限检查
        if data["user_id"] != requesting_user:
            # 检查是否有管理员权限
            if not await self._has_admin_access(requesting_user, session_id):
                self.logger.log(
                    action="unauthorized_access_attempt",
                    user_id=requesting_user,
                    session_id=session_id,
                    severity="warning"
                )
                raise PermissionError("无权访问此会话数据")

        # 3. 解密敏感数据
        slots = data.get("slots", {}).copy()
        for slot_name, encrypted_value in data.get("encrypted_slots", {}).items():
            slots[slot_name] = await self.encryption.decrypt(encrypted_value)

        # 4. 记录访问日志
        self.logger.log(
            action="slot_retrieval",
            user_id=requesting_user,
            session_id=session_id
        )

        return slots
```

### 12.3 数据保留与清理策略

```python
class DataRetentionManager:
    """数据保留管理器（v1.1新增）"""

    def __init__(self, storage: DataStorage):
        self.storage = storage

    async def apply_retention_policy(self) -> CleanupReport:
        """
        应用数据保留策略

        清理规则：
        1. 会话数据：30天后清理
        2. 敏感槽位：根据配置保留（30-365天）
        3. 日志数据：90天后清理
        4. 审计日志：7年后清理（合规要求）
        """
        report = CleanupReport()

        # 清理过期会话
        expired_sessions = await self._find_expired_sessions(days=30)
        for session in expired_sessions:
            await self._anonymize_session(session)
            report.sessions_anonymized += 1

        # 清理过期敏感数据
        for slot_name, config in DataMaskingRules.SENSITIVE_SLOTS.items():
            expired = await self._find_expired_slot_data(
                slot_name,
                days=config["retention_days"]
            )
            for record in expired:
                await self._secure_delete(record)
                report.records_deleted += 1

        return report

    async def _anonymize_session(self, session_id: str) -> None:
        """匿名化会话数据（保留统计信息，删除个人数据）"""
        await self.storage.execute("""
            UPDATE conversation_sessions
            SET
                user_id = hash(user_id),
                raw_queries = NULL,
                slots = NULL,
                encrypted_slots = NULL,
                is_anonymized = true
            WHERE session_id = ?
        """, session_id)

    async def _secure_delete(self, record: dict) -> None:
        """安全删除（覆写后再删除）"""
        # 1. 覆写敏感字段
        await self.storage.execute("""
            UPDATE slot_storage
            SET encrypted_value = ?
            WHERE id = ?
        """, "0" * 256, record["id"])

        # 2. 删除记录
        await self.storage.execute(
            "DELETE FROM slot_storage WHERE id = ?",
            record["id"]
        )


# 数据保留配置
RETENTION_CONFIG = {
    "session_data": {"days": 30, "action": "anonymize"},
    "conversation_history": {"days": 90, "action": "delete"},
    "audit_logs": {"days": 2555, "action": "archive"},  # 7年
    "sensitive_slots": {
        "critical": {"days": 30, "action": "secure_delete"},
        "high": {"days": 180, "action": "secure_delete"},
        "medium": {"days": 365, "action": "anonymize"},
    }
}
```

---

## 13. 人工介入机制（v1.1新增）

### 13.1 转人工触发条件

```python
class HumanHandoffTriggers:
    """转人工触发条件（v1.1新增）"""

    # 触发条件配置
    TRIGGERS = {
        # 连续澄清失败
        "repeated_clarification_failure": {
            "enabled": True,
            "max_rounds": 3,
            "severity": "medium"
        },

        # 敏感内容检测
        "sensitive_content": {
            "enabled": True,
            "categories": ["profanity", "political", "ecommerce_violation"],
            "severity": "high"
        },

        # 用户明确要求
        "explicit_request": {
            "enabled": True,
            "keywords": ["人工", "客服", "转人工", "找人工", "人工服务"],
            "severity": "low"
        },

        # 意图识别持续失败
        "persistent_intent_failure": {
            "enabled": True,
            "consecutive_failures": 3,
            "severity": "medium"
        },

        # 复杂业务场景
        "complex_scenario": {
            "enabled": True,
            "scenarios": ["multi_order_dispute", "legal_threat", "media_mention"],
            "severity": "high"
        },

        # VIP用户请求
        "vip_request": {
            "enabled": True,
            "vip_levels": [3, 4, 5],  # VIP等级
            "severity": "low"
        },

        # 情绪检测（愤怒、威胁）
        "negative_emotion": {
            "enabled": True,
            "emotion_types": ["angry", "threatening", "frustrated"],
            "confidence_threshold": 0.8,
            "severity": "medium"
        }
    }


class HandoffDecider:
    """转人工决策器（v1.1新增）"""

    def __init__(self, triggers: HumanHandoffTriggers):
        self.triggers = triggers
        self.failure_tracker: dict[str, int] = {}

    async def should_handoff(
        self,
        state: ConversationState,
        user_profile: dict | None = None
    ) -> HandoffDecision:
        """判断是否需要转人工"""

        # 检查1：用户明确要求
        if self._check_explicit_request(state.current_query):
            return HandoffDecision(
                should_handoff=True,
                reason="explicit_user_request",
                priority="normal",
                context={"user_message": state.current_query}
            )

        # 检查2：连续澄清失败
        if state.clarification_round >= self.triggers.TRIGGERS["repeated_clarification_failure"]["max_rounds"]:
            return HandoffDecision(
                should_handoff=True,
                reason="repeated_clarification_failure",
                priority="normal",
                context={"failed_slots": state.asked_slots}
            )

        # 检查3：敏感内容
        safety_check = await self._check_safety(state.current_query)
        if safety_check.is_violation:
            return HandoffDecision(
                should_handoff=True,
                reason="sensitive_content",
                priority="urgent",
                context={"violation_type": safety_check.violation_type}
            )

        # 检查4：VIP用户
        if user_profile and user_profile.get("vip_level") in \
           self.triggers.TRIGGERS["vip_request"]["vip_levels"]:
            # VIP用户在澄清失败时更快转人工
            if state.clarification_round >= 2:
                return HandoffDecision(
                    should_handoff=True,
                    reason="vip_fast_track",
                    priority="high",
                    context={"vip_level": user_profile.get("vip_level")}
                )

        # 检查5：持续识别失败
        session_id = state.session_id
        if state.ambiguity_type == "low_confidence":
            self.failure_tracker[session_id] = self.failure_tracker.get(session_id, 0) + 1
            if self.failure_tracker[session_id] >= \
               self.triggers.TRIGGERS["persistent_intent_failure"]["consecutive_failures"]:
                return HandoffDecision(
                    should_handoff=True,
                    reason="persistent_intent_failure",
                    priority="normal",
                    context={"failure_count": self.failure_tracker[session_id]}
                )
        else:
            self.failure_tracker[session_id] = 0

        return HandoffDecision(should_handoff=False)

    def _check_explicit_request(self, query: str) -> bool:
        """检查用户是否明确要求人工"""
        keywords = self.triggers.TRIGGERS["explicit_request"]["keywords"]
        return any(kw in query for kw in keywords)
```

### 13.2 无缝转接流程设计

```python
class HumanHandoffService:
    """人工转接服务（v1.1新增）"""

    def __init__(
        self,
        agent_queue: AgentQueue,
        context_transfer: ContextTransferService,
        notification_service: NotificationService
    ):
        self.agent_queue = agent_queue
        self.context_transfer = context_transfer
        self.notification = notification_service

    async def initiate_handoff(
        self,
        decision: HandoffDecision,
        state: ConversationState,
        user_profile: dict | None = None
    ) -> HandoffResult:
        """
        发起人工转接
        """
        # 1. 准备上下文摘要
        context_summary = await self._prepare_context_summary(state, user_profile)

        # 2. 选择合适的客服队列
        queue = self._select_queue(decision, user_profile)

        # 3. 创建转接工单
        ticket = await self._create_ticket(
            decision=decision,
            context=context_summary,
            queue=queue
        )

        # 4. 通知用户
        await self._notify_user(state.session_id, ticket)

        # 5. 更新对话状态
        await self._update_conversation_state(state, ticket)

        return HandoffResult(
            ticket_id=ticket.id,
            estimated_wait_time=ticket.estimated_wait,
            queue_position=ticket.queue_position
        )

    async def _prepare_context_summary(
        self,
        state: ConversationState,
        user_profile: dict | None
    ) -> ContextSummary:
        """准备上下文摘要供人工客服查看"""

        # 提取关键信息
        summary = ContextSummary(
            session_id=state.session_id,
            user_id=state.user_id,
            user_profile=user_profile,

            # 意图历史
            intent_history=[
                {
                    "primary": h.primary_intent,
                    "secondary": h.secondary_intent,
                    "slots": self._mask_sensitive_slots(h.slots)
                }
                for h in state.intent_history
            ],

            # 当前意图
            current_intent={
                "primary": state.current_intent.primary_intent,
                "secondary": state.current_intent.secondary_intent,
                "tertiary": state.current_intent.tertiary_intent,
                "slots": self._mask_sensitive_slots(state.current_intent.slots),
                "missing_slots": state.current_intent.missing_slots
            },

            # 对话历史（最近5轮）
            recent_dialogue=state.dialogue_history[-5:],

            # 澄清历史
            clarification_history=state.clarification_history,

            # 转人工原因
            handoff_reason=state.handoff_reason,

            # 建议处理方案
            suggested_actions=self._generate_suggestions(state)
        )

        return summary

    def _mask_sensitive_slots(self, slots: dict) -> dict:
        """脱敏处理槽位数据"""
        return DataMaskingRules.mask_slots_for_display(slots)

    def _select_queue(
        self,
        decision: HandoffDecision,
        user_profile: dict | None
    ) -> str:
        """选择合适的客服队列"""
        # VIP用户优先队列
        if user_profile and user_profile.get("vip_level", 0) >= 3:
            return "vip_priority"

        # 根据紧急程度
        if decision.priority == "urgent":
            return "urgent"

        # 根据业务域
        if decision.context and "primary_intent" in decision.context:
            intent = decision.context["primary_intent"]
            queue_map = {
                "AFTER_SALES": "after_sales",
                "ORDER": "order_support",
                "PAYMENT": "payment_support",
            }
            return queue_map.get(intent, "general")

        return "general"

    async def _notify_user(self, session_id: str, ticket: Ticket) -> None:
        """通知用户转接状态"""
        if ticket.queue_position <= 3:
            message = f"已为您转接人工客服，当前排队位置：{ticket.queue_position}，预计等待{ticket.estimated_wait}分钟。"
        else:
            message = f"已为您转接人工客服，当前排队人数较多，预计等待{ticket.estimated_wait}分钟。您也可以留下联系方式，我们会尽快回电。"

        await self.notification.send(session_id, message)
```

### 13.3 上下文传递机制

```python
class ContextTransferService:
    """上下文传递服务（v1.1新增）"""

    async def transfer_to_human_agent(
        self,
        session_id: str,
        agent_id: str
    ) -> TransferResult:
        """
        将对话上下文传递给人工客服
        """
        # 1. 加载完整对话上下文
        context = await self._load_full_context(session_id)

        # 2. 生成结构化摘要
        summary = self._generate_agent_summary(context)

        # 3. 推送到客服工作台
        await self._push_to_agent_workbench(agent_id, summary)

        # 4. 建立实时连接（可选）
        await self._establish_realtime_bridge(session_id, agent_id)

        return TransferResult(success=True)

    def _generate_agent_summary(self, context: FullContext) -> AgentSummary:
        """生成客服友好的摘要"""
        return AgentSummary(
            # 用户信息卡片
            user_card={
                "user_id": context.user_id,
                "vip_level": context.user_profile.get("vip_level"),
                "registration_time": context.user_profile.get("registration_time"),
                "order_count": context.user_profile.get("order_count"),
                "previous_tickets": context.user_profile.get("previous_tickets_count", 0)
            },

            # 问题摘要
            issue_summary={
                "primary_issue": self._extract_primary_issue(context),
                "related_orders": context.extracted_slots.get("order_sn"),
                "user_emotion": self._analyze_emotion(context.dialogue_history),
                "complexity_score": self._calculate_complexity(context)
            },

            # 已尝试的解决方案
            attempted_solutions=[
                {"action": h.action, "result": h.result}
                for h in context.system_actions
            ],

            # 建议回复模板
            suggested_responses=self._generate_response_templates(context),

            # 相关知识库文章
            related_kb_articles=self._find_related_kb(context)
        )

    async def _establish_realtime_bridge(
        self,
        session_id: str,
        agent_id: str
    ) -> None:
        """
        建立用户-系统-人工的实时桥接

        消息流向：
        用户 -> 意图识别系统 -> 人工客服
        人工客服 -> 意图识别系统 -> 用户
        """
        bridge = RealtimeBridge(
            session_id=session_id,
            agent_id=agent_id
        )

        # 注册消息处理器
        bridge.on_user_message = self._handle_user_message
        bridge.on_agent_message = self._handle_agent_message

        await bridge.start()

    async def _handle_user_message(
        self,
        session_id: str,
        message: str
    ) -> None:
        """处理用户消息（转人工后）"""
        # 可选择继续经过意图识别系统做分析辅助
        intent_analysis = await self.intent_service.recognize(message, session_id)

        # 将意图分析结果附加到消息中，供人工客服参考
        enriched_message = {
            "original": message,
            "intent_analysis": {
                "primary": intent_analysis.primary_intent,
                "confidence": intent_analysis.confidence,
                "extracted_slots": intent_analysis.slots
            }
        }

        # 转发给人工客服
        await self._forward_to_agent(session_id, enriched_message)
```

---

## 14. 附录

### 14.1 术语表

| 术语 | 定义 |
|------|------|
| 意图(Intent) | 用户输入的目的或目标 |
| 槽位(Slot) | 完成意图所需的具体信息片段 |
| 澄清(Clarification) | 系统主动提问以获取缺失信息 |
| Few-shot | 在Prompt中提供示例以引导模型 |
| Function Calling | LLM通过调用预定义函数输出结构化数据 |
| A/B测试 | 对照实验，比较两个版本的效果 |
| 脱敏 | 隐藏敏感信息的部分内容 |
| 回滚 | 撤销已执行的操作 |

### 14.2 参考文献

1. OpenAI Function Calling Documentation
2. 阿里云小蜜意图设计最佳实践
3. Rasa对话系统意图分类设计指南
4. GDPR数据保护条例（数据隐私参考）
5. ISO 27001信息安全管理标准

---

## 15. 评审记录

| 日期 | 评审人 | 意见 | 状态 |
|------|--------|------|------|
| | | | |

---

**文档状态**: 待评审
**版本**: v1.1
**更新日期**: 2025-01-09
**下次评审日期**: 待确定
