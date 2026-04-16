import uuid
from datetime import UTC, datetime

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.models.memory import AgentConfig
from app.models.observability import GraphExecutionLog
from app.models.prompt_effect_report import PromptEffectReport
from app.tasks.prompt_effect_tasks import _generate_monthly_report, _generate_single_report


@pytest.mark.asyncio
async def test_generate_single_report():
    agent_name = f"effect_agent_{uuid.uuid4().hex[:8]}"
    async with async_session_maker() as session:
        config = AgentConfig(
            agent_name=agent_name,
            system_prompt="prompt",
            confidence_threshold=0.7,
            max_retries=3,
            enabled=True,
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)

        log = GraphExecutionLog(
            thread_id="t1",
            user_id=1,
            final_agent=agent_name,
            confidence_score=0.88,
            needs_human_transfer=False,
            total_latency_ms=200,
            created_at=datetime(2026, 3, 15, tzinfo=UTC),
        )
        session.add(log)
        await session.commit()

        result = await _generate_single_report(session, agent_name, "2026-03")

        assert result["agent_name"] == agent_name
        assert result["report_month"] == "2026-03"
        assert result["total_sessions"] == 1
        assert result["transfer_rate"] == 0.0

        report = (
            await session.exec(
                select(PromptEffectReport).where(PromptEffectReport.agent_name == agent_name)
            )
        ).one_or_none()
        assert report is not None
        assert report.total_sessions == 1
        assert report.avg_confidence == 0.88


@pytest.mark.asyncio
async def test_generate_monthly_report_auto_discovers_agents():
    agent_name = f"auto_agent_{uuid.uuid4().hex[:8]}"
    async with async_session_maker() as session:
        config = AgentConfig(
            agent_name=agent_name,
            system_prompt="prompt",
            confidence_threshold=0.7,
            max_retries=3,
            enabled=True,
        )
        session.add(config)
        await session.commit()

        result = await _generate_monthly_report(report_month="2026-03")

        assert result["generated"] >= 1
        assert result["month"] == "2026-03"
        agent_names = [r["agent_name"] for r in result["reports"]]
        assert agent_name in agent_names


@pytest.mark.asyncio
async def test_generate_monthly_report_with_specific_agent():
    agent_name = f"specific_agent_{uuid.uuid4().hex[:8]}"
    async with async_session_maker() as session:
        config = AgentConfig(
            agent_name=agent_name,
            system_prompt="prompt",
            confidence_threshold=0.7,
            max_retries=3,
            enabled=True,
        )
        session.add(config)
        await session.commit()

        result = await _generate_monthly_report(agent_name=agent_name, report_month="2026-03")

        assert result["agent_name"] == agent_name
        assert result["report_month"] == "2026-03"
