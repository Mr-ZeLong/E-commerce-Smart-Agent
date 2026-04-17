import pytest

from app.evaluation.containment import containment_rate
from app.models.observability import GraphExecutionLog


def test_containment_rate_empty_records():
    assert containment_rate([]) == 0.0


def test_containment_rate_all_contained():
    records = [
        GraphExecutionLog(thread_id="t1", user_id=1, needs_human_transfer=False),
        GraphExecutionLog(thread_id="t2", user_id=1, needs_human_transfer=False),
    ]
    assert containment_rate(records) == pytest.approx(1.0)


def test_containment_rate_all_transferred():
    records = [
        GraphExecutionLog(thread_id="t3", user_id=1, needs_human_transfer=True),
        GraphExecutionLog(thread_id="t4", user_id=1, needs_human_transfer=True),
    ]
    assert containment_rate(records) == pytest.approx(0.0)


def test_containment_rate_partial():
    records = [
        GraphExecutionLog(thread_id="t5", user_id=1, needs_human_transfer=False),
        GraphExecutionLog(thread_id="t6", user_id=1, needs_human_transfer=True),
        GraphExecutionLog(thread_id="t7", user_id=1, needs_human_transfer=False),
    ]
    assert containment_rate(records) == pytest.approx(2 / 3)
