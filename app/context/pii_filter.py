"""Real-time PII detection and filtering for the E-commerce Smart Agent.

This module provides regex-based PII detection and redaction for sensitive
data including credit cards, phone numbers, ID numbers, and email addresses.
It supports both Chinese and international formats and includes GDPR compliance
utilities for data retention and right to deletion.

All PII detection is performed with compiled regex patterns. Audit logs record
*that* PII was detected and redacted, but never store the PII values themselves.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_CREDIT_CARD_RE = re.compile(
    r"""\b(?:
        4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}
      | 5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}
      | 3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}
      | 3(?:0[0-5]|[68]\d)\d[\s-]?\d{6}[\s-]?\d{4}
      | 6(?:011|5\d{2})[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}
      | (?:2131|1800|35\d{3})[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}
    )\b""",
    re.VERBOSE,
)

_CHINESE_MOBILE_RE = re.compile(
    r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}(?!\d)",
)

_INTERNATIONAL_PHONE_RE = re.compile(
    r"\+(?:\d{1,3}[-\s]?)?\d{1,4}[-\s]?\d{1,4}[-\s]?\d{1,9}",
)

_CHINESE_ID_RE = re.compile(
    r"\b\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b",
)

_PASSPORT_RE = re.compile(r"\b[A-Z]\d{7,8}\b|\b\d{9}\b")

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_PASSWORD_RE = re.compile(r"password[\s]*[:=][\s]*\S+", re.IGNORECASE)

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

_BANK_ACCOUNT_RE = re.compile(r"\b\d{8,20}\b(?![\dXx])")

_WEIGHTS_ID = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_CHECKSUM_ID = "10X98765432"


def _luhn_valid(digits: str) -> bool:
    if not digits or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(digits[::-1]):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _chinese_id_valid(id_number: str) -> bool:
    if len(id_number) != 18:
        return False
    body = id_number[:17]
    check = id_number[17].upper()
    if not body.isdigit():
        return False
    total = sum(int(body[i]) * _WEIGHTS_ID[i] for i in range(17))
    return _CHECKSUM_ID[total % 11] == check


@dataclass
class PIIDetectionResult:
    original_text: str
    redacted_text: str
    detections: dict[str, int] = field(default_factory=dict)
    has_pii: bool = False


class PIIFilter:
    _PLACEHOLDERS: dict[str, str] = {
        "credit_card": "[CREDIT_CARD_REDACTED]",
        "phone": "[PHONE_REDACTED]",
        "chinese_id": "[ID_REDACTED]",
        "passport": "[PASSPORT_REDACTED]",
        "email": "[EMAIL_REDACTED]",
        "password": "[PASSWORD_REDACTED]",
        "ssn": "[SSN_REDACTED]",
        "bank_account": "[BANK_ACCOUNT_REDACTED]",
    }

    def __init__(self) -> None:
        self._detection_count: dict[str, int] = {}

    def filter_text(self, text: str | None) -> PIIDetectionResult:
        if text is None:
            text = ""
        redacted = text
        detections: dict[str, int] = {}

        redacted, count = self._redact_credit_cards(redacted)
        if count:
            detections["credit_card"] = count

        redacted, count = self._redact_chinese_id(redacted)
        if count:
            detections["chinese_id"] = count

        redacted, count = self._redact_chinese_mobile(redacted)
        if count:
            detections["phone"] = detections.get("phone", 0) + count

        redacted, count = self._redact_international_phone(redacted)
        if count:
            detections["phone"] = detections.get("phone", 0) + count

        redacted, count = self._redact_passport(redacted)
        if count:
            detections["passport"] = count

        redacted, count = self._redact_email(redacted)
        if count:
            detections["email"] = count

        redacted, count = self._redact_password(redacted)
        if count:
            detections["password"] = count

        redacted, count = self._redact_ssn(redacted)
        if count:
            detections["ssn"] = count

        redacted, count = self._redact_bank_account(redacted)
        if count:
            detections["bank_account"] = count

        return PIIDetectionResult(
            original_text=text,
            redacted_text=redacted,
            detections=detections,
            has_pii=bool(detections),
        )

    def filter_dict(self, data: dict[str, Any], keys: list[str] | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in data.items():
            if keys is not None and k not in keys:
                result[k] = v
                continue
            if isinstance(v, str):
                result[k] = self.filter_text(v).redacted_text
            elif isinstance(v, dict):
                result[k] = self.filter_dict(v, keys=None)
            elif isinstance(v, list):
                result[k] = self.filter_list(v)
            else:
                result[k] = v
        return result

    def filter_list(self, items: list[Any]) -> list[Any]:
        result: list[Any] = []
        for item in items:
            if isinstance(item, str):
                result.append(self.filter_text(item).redacted_text)
            elif isinstance(item, dict):
                result.append(self.filter_dict(item, keys=None))
            elif isinstance(item, list):
                result.append(self.filter_list(item))
            else:
                result.append(item)
        return result

    async def afilter_text(self, text: str | None) -> PIIDetectionResult:
        return self.filter_text(text)

    async def afilter_dict(
        self, data: dict[str, Any], keys: list[str] | None = None
    ) -> dict[str, Any]:
        return self.filter_dict(data, keys)

    def _redact_credit_cards(self, text: str) -> tuple[str, int]:
        count = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            raw = match.group(0)
            digits = re.sub(r"\D", "", raw)
            if len(digits) < 13:
                return raw
            if _luhn_valid(digits):
                count += 1
                return self._PLACEHOLDERS["credit_card"]
            return raw

        return _CREDIT_CARD_RE.sub(_replace, text), count

    def _redact_chinese_mobile(self, text: str) -> tuple[str, int]:
        count = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return self._PLACEHOLDERS["phone"]

        return _CHINESE_MOBILE_RE.sub(_replace, text), count

    def _redact_international_phone(self, text: str) -> tuple[str, int]:
        count = 0
        already_redacted = self._PLACEHOLDERS["phone"]

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            raw = match.group(0)
            if already_redacted in raw:
                return raw
            digits = re.sub(r"\D", "", raw)
            if len(digits) < 7:
                return raw
            count += 1
            return self._PLACEHOLDERS["phone"]

        return _INTERNATIONAL_PHONE_RE.sub(_replace, text), count

    def _redact_chinese_id(self, text: str) -> tuple[str, int]:
        count = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            raw = match.group(0)
            if _chinese_id_valid(raw):
                count += 1
                return self._PLACEHOLDERS["chinese_id"]
            return raw

        return _CHINESE_ID_RE.sub(_replace, text), count

    def _redact_passport(self, text: str) -> tuple[str, int]:
        count = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return self._PLACEHOLDERS["passport"]

        return _PASSPORT_RE.sub(_replace, text), count

    def _redact_email(self, text: str) -> tuple[str, int]:
        count = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return self._PLACEHOLDERS["email"]

        return _EMAIL_RE.sub(_replace, text), count

    def _redact_password(self, text: str) -> tuple[str, int]:
        count = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return self._PLACEHOLDERS["password"]

        return _PASSWORD_RE.sub(_replace, text), count

    def _redact_ssn(self, text: str) -> tuple[str, int]:
        count = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return self._PLACEHOLDERS["ssn"]

        return _SSN_RE.sub(_replace, text), count

    def _redact_bank_account(self, text: str) -> tuple[str, int]:
        count = 0
        finance_keywords = [
            "account",
            "bank",
            "card",
            "account number",
            "bank account",
            "银行卡",
            "账号",
            "账户",
        ]
        lower_text = text.lower()
        has_finance_context = any(kw in lower_text for kw in finance_keywords)

        def _replace(match: re.Match[str]) -> str:
            nonlocal count
            raw = match.group(0)
            # Skip sequences that look like Chinese IDs (18 digits with date pattern)
            if re.match(
                r"\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]?", raw
            ):
                return raw
            if has_finance_context or len(raw) >= 16:
                count += 1
                return self._PLACEHOLDERS["bank_account"]
            return raw

        return _BANK_ACCOUNT_RE.sub(_replace, text), count


pii_filter = PIIFilter()


def log_pii_detection(
    user_id: int | None,
    thread_id: str | None,
    source: str,
    detections: dict[str, int],
) -> None:
    if not detections:
        return
    detection_summary = ", ".join(f"{k}={v}" for k, v in detections.items())
    logger.warning(
        "PII detected and redacted: user_id=%s thread_id=%s source=%s types=%s",
        user_id,
        thread_id,
        source,
        detection_summary,
    )


class GDPRComplianceManager:
    DEFAULT_RETENTION_DAYS: int = 90

    def __init__(self, retention_days: int | None = None) -> None:
        self.retention_days = retention_days or getattr(
            settings, "MEMORY_RETENTION_DAYS", self.DEFAULT_RETENTION_DAYS
        )

    def is_retention_expired(self, created_at_iso: str) -> bool:
        from datetime import UTC, datetime, timedelta

        try:
            created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
            return created < cutoff
        except (ValueError, TypeError):
            logger.warning("Invalid timestamp for retention check: %s", created_at_iso)
            return False

    async def delete_user_data(
        self,
        user_id: int,
        vector_manager: Any | None = None,
        db_session: Any | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "user_id": user_id,
            "deleted_vectors": 0,
            "deleted_structured": 0,
            "errors": [],
        }

        if vector_manager is not None:
            try:
                deleted = await self._delete_user_vectors(vector_manager, user_id)
                result["deleted_vectors"] = deleted
            except Exception as exc:
                logger.exception("Failed to delete vector memory for user %s", user_id)
                result["errors"].append(f"vector_memory: {exc}")

        if db_session is not None:
            try:
                deleted = await self._delete_user_structured_memory(db_session, user_id)
                result["deleted_structured"] = deleted
            except Exception as exc:
                logger.exception("Failed to delete structured memory for user %s", user_id)
                result["errors"].append(f"structured_memory: {exc}")

        logger.info(
            "GDPR deletion completed for user_id=%s: vectors=%s structured=%s errors=%s",
            user_id,
            result["deleted_vectors"],
            result["deleted_structured"],
            len(result["errors"]),
        )
        return result

    async def _delete_user_vectors(self, vector_manager: Any, user_id: int) -> int:
        from qdrant_client import models

        await vector_manager.ensure_collection()
        total_deleted = 0
        offset = None
        while True:
            batch, offset = await vector_manager.client.scroll(
                collection_name=vector_manager.COLLECTION_NAME,
                limit=1000,
                offset=offset,
                with_payload=True,
            )
            if not batch:
                break
            point_ids: list[Any] = [
                str(point.id)
                for point in batch
                if point.payload is not None and point.payload.get("user_id") == user_id
            ]
            if point_ids:
                await vector_manager.client.delete(
                    collection_name=vector_manager.COLLECTION_NAME,
                    points_selector=models.PointIdsList(points=point_ids),
                )
                total_deleted += len(point_ids)
            if offset is None:
                break
        return total_deleted

    async def _delete_user_structured_memory(self, db_session: Any, user_id: int) -> int:
        from sqlalchemy import text

        tables = [
            "user_profiles",
            "user_preferences",
            "interaction_summaries",
            "user_facts",
        ]
        total_deleted = 0
        for table in tables:
            stmt = text(f"DELETE FROM {table} WHERE user_id = :user_id")  # noqa: S608
            result = await db_session.exec(stmt)
            total_deleted += result.rowcount if hasattr(result, "rowcount") else 0
        await db_session.commit()
        return total_deleted


def filter_text(text: str | None) -> PIIDetectionResult:
    return pii_filter.filter_text(text)


async def afilter_text(text: str | None) -> PIIDetectionResult:
    return await pii_filter.afilter_text(text)


def filter_dict(data: dict[str, Any], keys: list[str] | None = None) -> dict[str, Any]:
    return pii_filter.filter_dict(data, keys)


async def afilter_dict(data: dict[str, Any], keys: list[str] | None = None) -> dict[str, Any]:
    return await pii_filter.afilter_dict(data, keys)
