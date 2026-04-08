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
