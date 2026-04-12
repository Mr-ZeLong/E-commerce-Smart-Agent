import hashlib
import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.experiment import (
    Experiment,
    ExperimentAssignment,
    ExperimentStatus,
    ExperimentVariant,
)

logger = logging.getLogger(__name__)


def _deterministic_hash(user_id: str, experiment_key: str) -> int:
    raw = f"{user_id}:{experiment_key}".encode()
    return int(hashlib.md5(raw).hexdigest(), 16)


class ExperimentAssigner:
    async def assign(self, user_id: str, experiment_key: str, db: AsyncSession) -> str | None:
        result = await db.exec(
            select(Experiment).where(
                Experiment.name == experiment_key,
                Experiment.status == ExperimentStatus.RUNNING.value,
            )
        )
        experiment = result.one_or_none()
        if not experiment:
            return None
        assert experiment.id is not None

        variants_result = await db.exec(
            select(ExperimentVariant).where(ExperimentVariant.experiment_id == experiment.id)
        )
        variants = list(variants_result.all())
        if not variants:
            return None

        total_weight = sum(v.weight for v in variants)
        if total_weight <= 0:
            return None

        hash_value = _deterministic_hash(user_id, experiment_key)
        target = hash_value % total_weight
        cumulative = 0
        chosen = variants[0]
        for v in variants:
            cumulative += v.weight
            if target < cumulative:
                chosen = v
                break
        assert chosen.id is not None

        user_id_int = int(user_id) if user_id.isdigit() else 0
        existing = await db.exec(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment.id,
                ExperimentAssignment.user_id == user_id_int,
            )
        )
        if not existing.one_or_none():
            assignment = ExperimentAssignment(
                experiment_id=experiment.id,
                variant_id=chosen.id,
                user_id=user_id_int,
            )
            db.add(assignment)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                logger.debug("Experiment assignment race condition for user %s", user_id)
        return chosen.name
