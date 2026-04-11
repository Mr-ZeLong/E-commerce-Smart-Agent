import re
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def build_thread_id(user_id: int, client_thread_id: str) -> str:
    prefix = f"{user_id}__"
    if client_thread_id.startswith(prefix):
        return client_thread_id[:128]
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", client_thread_id)
    safe_id = safe_id[:80]
    return f"{prefix}{safe_id}"[:128]
