import logging
from typing import Any

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.experiment import (
    Experiment,
    ExperimentAssignment,
    ExperimentStatus,
    ExperimentVariant,
)

logger = logging.getLogger(__name__)


class ExperimentService:
    async def create_experiment(
        self,
        db: AsyncSession,
        name: str,
        description: str | None,
        variants: list[dict[str, Any]],
    ) -> Experiment:
        experiment = Experiment(
            name=name, description=description, status=ExperimentStatus.DRAFT.value
        )
        db.add(experiment)
        await db.flush()
        await db.refresh(experiment)
        assert experiment.id is not None
        for v in variants:
            variant = ExperimentVariant(
                experiment_id=experiment.id,
                name=v["name"],
                weight=v.get("weight", 1),
                system_prompt=v.get("system_prompt"),
                llm_model=v.get("llm_model"),
                retriever_top_k=v.get("retriever_top_k"),
                reranker_enabled=v.get("reranker_enabled"),
                extra_config=v.get("extra_config"),
                memory_context_config=v.get("memory_context_config"),
            )
            db.add(variant)
        await db.commit()
        await db.refresh(experiment)
        return experiment

    async def get_experiment(self, db: AsyncSession, experiment_id: int) -> Experiment | None:
        result = await db.exec(select(Experiment).where(Experiment.id == experiment_id))
        return result.one_or_none()

    async def list_experiments(
        self,
        db: AsyncSession,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Experiment]:
        stmt = select(Experiment).order_by(desc(Experiment.created_at))
        if status:
            stmt = stmt.where(Experiment.status == status)
        stmt = stmt.offset(offset).limit(limit)
        result = await db.exec(stmt)
        return list(result.all())

    async def set_status(self, db: AsyncSession, experiment_id: int, status: str) -> bool:
        experiment = await self.get_experiment(db, experiment_id)
        if not experiment:
            return False
        experiment.status = status
        db.add(experiment)
        await db.commit()
        return True

    async def get_variants(self, db: AsyncSession, experiment_id: int) -> list[ExperimentVariant]:
        result = await db.exec(
            select(ExperimentVariant).where(ExperimentVariant.experiment_id == experiment_id)
        )
        return list(result.all())

    async def get_results(self, db: AsyncSession, experiment_id: int) -> list[dict[str, Any]]:
        variants = await self.get_variants(db, experiment_id)
        results = []
        for v in variants:
            count_result = await db.exec(
                select(ExperimentAssignment).where(ExperimentAssignment.variant_id == v.id)
            )
            count = len(count_result.all())
            results.append(
                {
                    "variant_id": v.id,
                    "variant_name": v.name,
                    "weight": v.weight,
                    "assignments": count,
                }
            )
        return results
