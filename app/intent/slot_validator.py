"""槽位验证器

检查槽位完整性，按P0/P1/P2优先级管理，识别缺失槽位。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.intent.config import SLOT_PRIORITY_CONFIG
from app.intent.models import IntentResult, SlotPriority


@dataclass
class SlotValidationResult:
    """槽位验证结果"""

    is_complete: bool  # 是否完整（所有P0槽位已填充）
    missing_slots: list[str] = field(default_factory=list)  # 缺失的槽位列表
    missing_p0_slots: list[str] = field(default_factory=list)  # 缺失的P0槽位
    missing_p1_slots: list[str] = field(default_factory=list)  # 缺失的P1槽位
    missing_p2_slots: list[str] = field(default_factory=list)  # 缺失的P2槽位
    filled_slots: list[str] = field(default_factory=list)  # 已填充的槽位列表
    suggestions: dict[str, list[str]] = field(default_factory=dict)  # 槽位推荐值

    def __repr__(self) -> str:
        status = "完整" if self.is_complete else f"缺失 {len(self.missing_slots)} 个槽位"
        return f"<SlotValidationResult: {status}>"


class SlotValidator:
    """槽位验证器"""

    # 槽位推荐值配置
    SLOT_SUGGESTIONS: dict[str, list[str]] = {
        "action_type": ["REFUND", "EXCHANGE", "REPAIR"],
        "reason_category": ["质量问题", "尺寸不合适", "不喜欢", "发错货", "少件/漏发"],
        "query_type": ["状态", "金额", "物流", "详情"],
        "modify_field": ["地址", "电话", "收件人"],
        "policy_topic": ["退货政策", "换货政策", "运费说明", "售后时效"],
        "compare_aspect": ["价格", "规格", "评价", "销量"],
    }

    def _get_config(self, primary_key: str, secondary_key: str) -> dict[str, list[str]] | None:
        """获取指定意图组合的槽位配置

        Args:
            primary_key: 主意图键
            secondary_key: 次意图键

        Returns:
            dict[str, list[str]] | None: 槽位优先级配置，不存在则返回None
        """
        if (
            primary_key in SLOT_PRIORITY_CONFIG
            and secondary_key in SLOT_PRIORITY_CONFIG[primary_key]
        ):
            return SLOT_PRIORITY_CONFIG[primary_key][secondary_key]
        return None

    def _check_priority_slots(
        self,
        slots: dict[str, Any],
        config: dict[str, list[str]],
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        """按优先级检查槽位填充状态

        Args:
            slots: 当前槽位值
            config: 槽位优先级配置

        Returns:
            tuple: (p0缺失, p1缺失, p2缺失, 已填充)
        """
        p0_missing = []
        p1_missing = []
        p2_missing = []
        filled_slots = []

        # 检查P0槽位
        for slot_name in config.get("P0", []):
            if self._is_empty_value(slots.get(slot_name)):
                p0_missing.append(slot_name)
            else:
                filled_slots.append(slot_name)

        # 检查P1槽位
        for slot_name in config.get("P1", []):
            if self._is_empty_value(slots.get(slot_name)):
                p1_missing.append(slot_name)
            else:
                filled_slots.append(slot_name)

        # 检查P2槽位
        for slot_name in config.get("P2", []):
            if self._is_empty_value(slots.get(slot_name)):
                p2_missing.append(slot_name)
            else:
                filled_slots.append(slot_name)

        return p0_missing, p1_missing, p2_missing, filled_slots

    def _is_empty_value(self, value: Any) -> bool:
        """检查值是否为空（None或空字符串）

        Args:
            value: 要检查的值

        Returns:
            bool: 是否为空值
        """
        return value is None or value == ""

    def _generate_suggestions(self, missing_slots: list[str]) -> dict[str, list[str]]:
        """为缺失槽位生成推荐值

        Args:
            missing_slots: 缺失的槽位列表

        Returns:
            dict[str, list[str]]: 槽位推荐值映射
        """
        suggestions = {}
        for slot_name in missing_slots:
            if slot_name in self.SLOT_SUGGESTIONS:
                suggestions[slot_name] = self.SLOT_SUGGESTIONS[slot_name]
        return suggestions

    def validate(self, result: IntentResult) -> SlotValidationResult:
        """验证槽位完整性

        Args:
            result: 意图识别结果

        Returns:
            SlotValidationResult: 验证结果
        """
        primary_key = result.primary_intent.value
        secondary_key = result.secondary_intent.value
        slots = result.slots

        # 获取配置
        config = self._get_config(primary_key, secondary_key)

        if config is None:
            # 没有配置，视为完整
            return SlotValidationResult(is_complete=True)

        # 按优先级检查槽位
        p0_missing, p1_missing, p2_missing, filled_slots = self._check_priority_slots(
            slots or {}, config
        )

        # 合并所有缺失槽位（按优先级排序）
        missing_slots = p0_missing + p1_missing + p2_missing

        # 生成推荐值
        suggestions = self._generate_suggestions(missing_slots)

        return SlotValidationResult(
            is_complete=len(p0_missing) == 0,
            missing_slots=missing_slots,
            missing_p0_slots=p0_missing,
            missing_p1_slots=p1_missing,
            missing_p2_slots=p2_missing,
            filled_slots=filled_slots,
            suggestions=suggestions,
        )

    def get_next_missing_slot(self, result: SlotValidationResult) -> str | None:
        """获取下一个缺失槽位（按P0/P1/P2优先级）

        Args:
            result: 槽位验证结果

        Returns:
            str | None: 下一个缺失的槽位名称，如果没有则返回None
        """
        all_missing = result.missing_p0_slots + result.missing_p1_slots + result.missing_p2_slots
        return all_missing[0] if all_missing else None

    def merge_slots(
        self,
        existing: dict[str, Any],
        new_slots: dict[str, Any],
        overwrite: bool = True,
    ) -> dict[str, Any]:
        """合并槽位

        Args:
            existing: 现有槽位
            new_slots: 新槽位
            overwrite: 是否覆盖已有值

        Returns:
            dict[str, Any]: 合并后的槽位
        """
        merged = dict(existing)

        for key, value in new_slots.items():
            if not self._is_empty_value(value) and (
                overwrite or self._is_empty_value(merged.get(key))
            ):
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
        for _primary, secondary_config in SLOT_PRIORITY_CONFIG.items():
            for _secondary, priorities in secondary_config.items():
                for priority, slots in priorities.items():
                    if slot_name in slots:
                        return SlotPriority(priority)

        return None
