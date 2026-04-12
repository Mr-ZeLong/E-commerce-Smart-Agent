from app.graph.parallel import build_parallel_sends, plan_dispatch
from app.models.state import make_agent_state


class TestPlanDispatch:
    def test_done_when_all_completed(self):
        mode, targets = plan_dispatch(
            agent_queue=["order_agent", "policy_agent"],
            intent_queue=["ORDER", "POLICY"],
            completed=["order_agent", "policy_agent"],
        )
        assert mode == "done"
        assert targets == []

    def test_parallel_when_all_independent(self):
        mode, targets = plan_dispatch(
            agent_queue=["order_agent", "policy_agent"],
            intent_queue=["ORDER", "POLICY"],
            completed=[],
        )
        assert mode == "parallel"
        assert targets == ["order_agent", "policy_agent"]

    def test_serial_when_dependent(self):
        mode, targets = plan_dispatch(
            agent_queue=["cart", "payment"],
            intent_queue=["CART", "PAYMENT"],
            completed=[],
        )
        assert mode == "serial"
        assert targets == ["cart"]

    def test_partial_completion_triggers_parallel_for_remaining(self):
        mode, targets = plan_dispatch(
            agent_queue=["order_agent", "policy_agent", "logistics"],
            intent_queue=["ORDER", "POLICY", "LOGISTICS"],
            completed=["order_agent"],
        )
        assert mode == "parallel"
        assert targets == ["policy_agent", "logistics"]

    def test_serial_advances_after_first_completed(self):
        mode, targets = plan_dispatch(
            agent_queue=["cart", "payment"],
            intent_queue=["CART", "PAYMENT"],
            completed=["cart"],
        )
        assert mode == "serial"
        assert targets == ["payment"]


class TestBuildParallelSends:
    def test_builds_sends_for_each_agent(self):
        state = make_agent_state(question="test", thread_id="t1")
        sends = build_parallel_sends(["order_agent", "policy_agent"], state)
        assert len(sends) == 2
        assert sends[0].node == "order_agent"
        assert sends[1].node == "policy_agent"
        assert sends[0].arg == {}
        assert sends[1].arg == {}

    def test_empty_list(self):
        state = make_agent_state(question="test", thread_id="t1")
        sends = build_parallel_sends([], state)
        assert sends == []
