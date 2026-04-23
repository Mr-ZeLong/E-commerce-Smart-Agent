"""Tests for Prometheus metrics module.

Verifies that all custom metrics can be recorded and that the /metrics
endpoint returns valid Prometheus exposition format.
"""

from unittest.mock import patch

import pytest

from app.observability.metrics import (
    AGENT_CONTEXT_TOKENS,
    CHAT_ERRORS_TOTAL,
    CHAT_LATENCY_SECONDS,
    CHAT_REQUESTS_TOTAL,
    CONFIDENCE_SCORE,
    CONTEXT_UTILIZATION_RATIO,
    HALLUCINATION_RATE,
    HUMAN_TRANSFERS_TOTAL,
    INTENT_ACCURACY,
    NODE_LATENCY_SECONDS,
    RAG_PRECISION,
    TOKEN_USAGE_TOTAL,
    get_metrics_response,
    record_agent_context_tokens,
    record_chat_error,
    record_chat_latency,
    record_chat_request,
    record_confidence_score,
    record_context_utilization,
    record_human_transfer,
    record_node_latency,
    record_token_usage,
    set_hallucination_rate,
    set_intent_accuracy,
    set_rag_precision,
)


class TestRecordChatRequest:
    def test_record_chat_request_with_labels(self):
        before = CHAT_REQUESTS_TOTAL.labels(
            intent_category="ORDER", final_agent="order_agent"
        )._value.get()
        record_chat_request(intent_category="ORDER", final_agent="order_agent")
        after = CHAT_REQUESTS_TOTAL.labels(
            intent_category="ORDER", final_agent="order_agent"
        )._value.get()
        assert after == before + 1

    def test_record_chat_request_defaults(self):
        before = CHAT_REQUESTS_TOTAL.labels(
            intent_category="unknown", final_agent="unknown"
        )._value.get()
        record_chat_request()
        after = CHAT_REQUESTS_TOTAL.labels(
            intent_category="unknown", final_agent="unknown"
        )._value.get()
        assert after == before + 1


class TestRecordChatError:
    def test_record_chat_error(self):
        before = CHAT_ERRORS_TOTAL.labels(error_type="runtime")._value.get()
        record_chat_error("runtime")
        after = CHAT_ERRORS_TOTAL.labels(error_type="runtime")._value.get()
        assert after == before + 1


class TestRecordChatLatency:
    def test_record_chat_latency(self):
        before = CHAT_LATENCY_SECONDS.labels(final_agent="policy_agent")._sum.get()
        record_chat_latency(latency_seconds=0.25, final_agent="policy_agent")
        after = CHAT_LATENCY_SECONDS.labels(final_agent="policy_agent")._sum.get()
        assert after == pytest.approx(before + 0.25)

    def test_record_chat_latency_default_agent(self):
        before = CHAT_LATENCY_SECONDS.labels(final_agent="unknown")._sum.get()
        record_chat_latency(latency_seconds=1.0)
        after = CHAT_LATENCY_SECONDS.labels(final_agent="unknown")._sum.get()
        assert after == pytest.approx(before + 1.0)


class TestRecordNodeLatency:
    def test_record_node_latency(self):
        before = NODE_LATENCY_SECONDS.labels(node_name="router_node")._sum.get()
        record_node_latency(node_name="router_node", latency_seconds=0.05)
        after = NODE_LATENCY_SECONDS.labels(node_name="router_node")._sum.get()
        assert after == pytest.approx(before + 0.05)


class TestRecordTokenUsage:
    def test_record_token_usage(self):
        before = TOKEN_USAGE_TOTAL.labels(agent="order_agent")._value.get()
        record_token_usage(tokens=150, agent="order_agent")
        after = TOKEN_USAGE_TOTAL.labels(agent="order_agent")._value.get()
        assert after == before + 150

    def test_record_token_usage_default(self):
        before = TOKEN_USAGE_TOTAL.labels(agent="unknown")._value.get()
        record_token_usage(tokens=50)
        after = TOKEN_USAGE_TOTAL.labels(agent="unknown")._value.get()
        assert after == before + 50


class TestRecordContextUtilization:
    def test_record_context_utilization(self):
        record_context_utilization(0.75)
        value = CONTEXT_UTILIZATION_RATIO._value.get()
        assert value == pytest.approx(0.75)


class TestRecordHumanTransfer:
    def test_record_human_transfer(self):
        before = HUMAN_TRANSFERS_TOTAL.labels(reason="low_confidence")._value.get()
        record_human_transfer(reason="low_confidence")
        after = HUMAN_TRANSFERS_TOTAL.labels(reason="low_confidence")._value.get()
        assert after == before + 1

    def test_record_human_transfer_default(self):
        before = HUMAN_TRANSFERS_TOTAL.labels(reason="unknown")._value.get()
        record_human_transfer()
        after = HUMAN_TRANSFERS_TOTAL.labels(reason="unknown")._value.get()
        assert after == before + 1


class TestRecordConfidenceScore:
    def test_record_confidence_score(self):
        before = CONFIDENCE_SCORE._sum.get()
        record_confidence_score(0.85)
        after = CONFIDENCE_SCORE._sum.get()
        assert after == pytest.approx(before + 0.85)


class TestSetIntentAccuracy:
    def test_set_intent_accuracy(self):
        set_intent_accuracy(0.92, intent_category="ORDER")
        value = INTENT_ACCURACY.labels(intent_category="ORDER")._value.get()
        assert value == pytest.approx(0.92)

    def test_set_intent_accuracy_default(self):
        set_intent_accuracy(0.88)
        value = INTENT_ACCURACY.labels(intent_category="overall")._value.get()
        assert value == pytest.approx(0.88)


class TestSetRagPrecision:
    def test_set_rag_precision(self):
        set_rag_precision(0.78)
        value = RAG_PRECISION._value.get()
        assert value == pytest.approx(0.78)


class TestSetHallucinationRate:
    def test_set_hallucination_rate(self):
        set_hallucination_rate(0.02)
        value = HALLUCINATION_RATE._value.get()
        assert value == pytest.approx(0.02)


class TestRecordAgentContextTokens:
    def test_record_agent_context_tokens(self):
        record_agent_context_tokens(tokens=512, agent_name="order_agent")
        value = AGENT_CONTEXT_TOKENS.labels(agent_name="order_agent")._value.get()
        assert value == pytest.approx(512)

    def test_record_agent_context_tokens_default_agent(self):
        record_agent_context_tokens(tokens=256)
        value = AGENT_CONTEXT_TOKENS.labels(agent_name="unknown")._value.get()
        assert value == pytest.approx(256)


class TestGetMetricsResponse:
    def test_returns_bytes_and_content_type(self):
        body, content_type = get_metrics_response()
        assert isinstance(body, bytes)
        assert content_type.startswith("text/plain; version=")
        assert "charset=utf-8" in content_type
        assert b"chat_requests_total" in body


class TestMetricsEndpointIntegration:
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        response = await client.get("/metrics", follow_redirects=True)
        assert response.status_code == 200
        ct = response.headers["content-type"]
        assert ct.startswith("text/plain; version=")
        assert "charset=utf-8" in ct
        assert b"chat_requests_total" in response.content
        assert b"chat_latency_seconds_bucket" in response.content

    @pytest.mark.asyncio
    async def test_metrics_after_chat_request(self, client):
        record_chat_request(intent_category="POLICY", final_agent="policy_agent")
        record_chat_latency(latency_seconds=0.5, final_agent="policy_agent")

        response = await client.get("/metrics", follow_redirects=True)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'chat_requests_total{intent_category="POLICY",final_agent="policy_agent"}' in content
        assert 'chat_latency_seconds_sum{final_agent="policy_agent"}' in content


class TestExecutionLoggerIntegration:
    @pytest.mark.asyncio
    async def test_log_graph_execution_records_metrics(
        self,
        db_session,
    ):
        from app.observability.execution_logger import log_graph_execution

        with (
            patch("app.observability.execution_logger.record_chat_request") as mock_req,
            patch("app.observability.execution_logger.record_confidence_score") as mock_conf,
            patch("app.observability.execution_logger.record_human_transfer") as mock_transfer,
            patch("app.observability.execution_logger.record_context_utilization") as mock_ctx,
            patch("app.observability.execution_logger.record_token_usage") as mock_tok,
        ):
            await log_graph_execution(
                session=db_session,
                thread_id="t-metrics",
                user_id=1,
                intent_category="ORDER",
                final_agent="order_agent",
                confidence_score=0.85,
                needs_human_transfer=True,
                total_latency_ms=1200,
                context_tokens=2048,
                context_utilization=0.75,
            )

            mock_req.assert_called_once_with(intent_category="ORDER", final_agent="order_agent")
            mock_conf.assert_called_once_with(0.85)
            mock_transfer.assert_called_once_with(reason="low_confidence")
            mock_ctx.assert_called_once_with(0.75)
            mock_tok.assert_called_once_with(tokens=2048, agent="order_agent")


class TestLatencyTrackerIntegration:
    @pytest.mark.asyncio
    async def test_compute_node_latency_stats_records_prometheus(self, db_session):
        from app.models.observability import GraphExecutionLog, GraphNodeLog
        from app.models.user import User
        from app.observability.latency_tracker import compute_node_latency_stats

        user = User(
            username="metrics_test",
            password_hash=User.hash_password("secret"),
            email="metrics@test.com",
            full_name="Metrics Test",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.id is not None

        exec_log = GraphExecutionLog(thread_id="t-latency", user_id=user.id)
        db_session.add(exec_log)
        await db_session.commit()
        await db_session.refresh(exec_log)
        assert exec_log.id is not None

        db_session.add(
            GraphNodeLog(
                execution_id=exec_log.id,
                node_name="test_node",
                latency_ms=100,
            )
        )
        await db_session.commit()

        with patch("app.observability.latency_tracker.record_node_latency") as mock_record:
            await compute_node_latency_stats(db_session)
            mock_record.assert_called_once_with(node_name="test_node", latency_seconds=0.1)
