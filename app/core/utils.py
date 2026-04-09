from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))
