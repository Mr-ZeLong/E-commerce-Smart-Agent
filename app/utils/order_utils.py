import re

from app.models.refund import RefundReason

ORDER_SN_PATTERN = re.compile(r"(SN\d+)", re.IGNORECASE)


def extract_order_sn(text: str) -> str | None:
    """Extract order SN from text."""
    match = ORDER_SN_PATTERN.search(text)
    return match.group(1).upper() if match else None


def classify_refund_reason(text: str) -> RefundReason:
    """Classify refund reason from text."""
    if "质量" in text or "破损" in text:
        return RefundReason.QUALITY_ISSUE
    elif "尺码" in text or "大小" in text or "不合适" in text:
        return RefundReason.SIZE_NOT_FIT
    elif "不符" in text or "描述" in text:
        return RefundReason.NOT_AS_DESCRIBED
    else:
        return RefundReason.OTHER
