"""槽位验证器

检查槽位完整性，按P0/P1/P2优先级管理，识别缺失槽位。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.intent.models import IntentCategory, IntentAction, SlotPriority
from app.intent.config import get_required_slots, get_slot_priority


@dataclass
class SlotValidationResult:
    """槽位验证结果"""
    is_complete: bool  # 是否完整（所有P0槽位已填充）
    missing_slots: list[str] = field(default_factory=list)  # 缺失的槽位列表
    p0_missing: list[str] = field(default_factory=list)  # 缺失的P0槽位
    p1_missing: list[str] = field(default_factory=list)  # 缺失的P1槽位
    p2_missing: list[str] = field(default_factory=list)  # 缺失的P2槽位
    suggestions: dict[str, list[str]] = field(default_factory=dict)  # 槽位推荐值


class SlotValidator:
    """槽位验证器"""

    # 槽位推荐值配置
    SLOT_SUGGESTIONS: dict[str, list[str]] = {
        "action_type": ["退款", "换货", "维修"],
        "reason_category": ["质量问题", "尺寸不合适", "不喜欢", "发错货", "少件/漏发"],
        "query_type": ["状态", "金额", "物流", "详情"],
        "modify_field": ["地址", "电话", "收件人"],
        "policy_topic": ["退货政策", "换货政策", "运费说明", "售后时效"],
        "compare_aspect": ["价格", "规格", "评价", "销量"],
    }

    def __init__(self):
        """初始化槽位验证器"""
        pass

    def validate(
        self,
        primary: IntentCategory,
        secondary: IntentAction,
        slots: dict[str, Any],
    ) -> SlotValidationResult:
        """验证槽位完整性

        Args:
            primary: 一级意图
            secondary: 二级意图
            slots: 当前已填充的槽位

        Returns:
            SlotValidationResult: 验证结果
        """
        # 获取所有优先级槽位配置
        from app.intent.config import SLOT_PRIORITY_CONFIG

        primary_key = primary.value
        secondary_key = secondary.value

        p0_missing = []
        p1_missing = []
        p2_missing = []

        # 检查配置是否存在
        if (
            primary_key in SLOT_PRIORITY_CONFIG
            and secondary_key in SLOT_PRIORITY_CONFIG[primary_key]
        ):
            config = SLOT_PRIORITY_CONFIG[primary_key][secondary_key]

            # 检查P0槽位
            for slot_name in config.get("P0", []):
                if slot_name not in slots or slots[slot_name] is None or slots[slot_name] == "":
                    p0_missing.append(slot_name)

            # 检查P1槽位
            for slot_name in config.get("P1", []):
                if slot_name not in slots or slots[slot_name] is None or slots[slot_name] == "":
                    p1_missing.append(slot_name)

            # 检查P2槽位
            for slot_name in config.get("P2", []):
                if slot_name not in slots or slots[slot_name] is None or slots[slot_name] == "":
                    p2_missing.append(slot_name)

        # 合并所有缺失槽位（按优先级排序）
        missing_slots = p0_missing + p1_missing + p2_missing

        # 生成推荐值
        suggestions = {}
        for slot_name in missing_slots:
            if slot_name in self.SLOT_SUGGESTIONS:
                suggestions[slot_name] = self.SLOT_SUGGESTIONS[slot_name]

        return SlotValidationResult(
            is_complete=len(p0_missing) == 0,
            missing_slots=missing_slots,
            p0_missing=p0_missing,
            p1_missing=p1_missing,
            p2_missing=p2_missing,
            suggestions=suggestions,
        )

    def get_next_missing_slot(
        self,
        primary: IntentCategory,
        secondary: IntentAction,
        slots: dict[str, Any],
        exclude_slots: list[str] | None = None,
    ) -> str | None:
        """获取下一个缺失槽位（按P0/P1/P2优先级）

        Args:
            primary: 一级意图
            secondary: 二级意图
            slots: 当前已填充的槽位
            exclude_slots: 要排除的槽位列表（如用户已拒绝的槽位）

        Returns:
            str | None: 下一个缺失的槽位名称，如果没有则返回None
        """
        result = self.validate(primary, secondary, slots)
        exclude_set = set(exclude_slots or [])

        # 按P0 -> P1 -> P2顺序查找第一个缺失槽位
        for slot in result.p0_missing:
            if slot not in exclude_set:
                return slot

        for slot in result.p1_missing:
            if slot not in exclude_set:
                return slot

        for slot in result.p2_missing:
            if slot not in exclude_set:
                return slot

        return None

    def merge_slots(
        self,
        existing_slots: dict[str, Any],
        new_slots: dict[str, Any],
        overwrite: bool = True,
    ) -> dict[str, Any]:
        """合并槽位

        Args:
            existing_slots: 现有槽位
            new_slots: 新槽位
            overwrite: 是否覆盖已有值

        Returns:
            dict[str, Any]: 合并后的槽位
        """
        merged = dict(existing_slots)

        for key, value in new_slots.items():
            if value is not None and value != "":
                if overwrite or key not in merged or merged[key] is None or merged[key] == "":
                    merged[key] = value

        return merged

    def get_slot_suggestions(self, slot_name: str) -> list[str]:
        """获取槽位推荐值

        Args:
            slot_name: 槽位名称

        Returns:
            list[str]: 推荐值列表
        """
        return self.SLOT_SUGGESTIONS.get(slot_name, [])

    def get_priority(self, slot_name: str) -> SlotPriority | None:
        """获取槽位优先级

        Args:
            slot_name: 槽位名称

        Returns:
            SlotPriority | None: 槽位优先级
        """
        # 遍历所有配置查找槽位优先级
        from app.intent.config import SLOT_PRIORITY_CONFIG

        for primary, secondary_config in SLOT_PRIORITY_CONFIG.items():
            for secondary, priorities in secondary_config.items():
                for priority, slots in priorities.items():
                    if slot_name in slots:
                        return SlotPriority(priority)

        return None
