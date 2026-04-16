import pytest

from app.models.experiment import Experiment, ExperimentStatus, ExperimentVariant
from app.services.experiment_assigner import ExperimentAssigner, _deterministic_hash


@pytest.mark.asyncio
async def test_deterministic_hash_is_consistent():
    h1 = _deterministic_hash("user_123", "exp_a")
    h2 = _deterministic_hash("user_123", "exp_a")
    assert h1 == h2
    assert h1 != _deterministic_hash("user_123", "exp_b")


@pytest.mark.asyncio
async def test_assign_returns_none_when_experiment_not_found(db_session):
    assigner = ExperimentAssigner()
    result = await assigner.assign("123", "nonexistent_exp", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_assign_returns_none_when_no_variants(db_session):
    assigner = ExperimentAssigner()
    exp = Experiment(name="exp_no_variants", status=ExperimentStatus.RUNNING.value)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.id is not None
    result = await assigner.assign("123", "exp_no_variants", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_assign_chooses_variant_based_on_weight(db_session):
    assigner = ExperimentAssigner()
    exp = Experiment(name="exp_weighted", status=ExperimentStatus.RUNNING.value)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.id is not None

    v1 = ExperimentVariant(experiment_id=exp.id, name="control", weight=1)
    v2 = ExperimentVariant(experiment_id=exp.id, name="treatment", weight=1)
    db_session.add_all([v1, v2])
    await db_session.flush()
    await db_session.refresh(v1)
    await db_session.refresh(v2)

    result = await assigner.assign("999", "exp_weighted", db_session)
    assert result in {v1.id, v2.id}


@pytest.mark.asyncio
async def test_assign_creates_assignment_record(db_session):
    assigner = ExperimentAssigner()
    exp = Experiment(name="exp_record", status=ExperimentStatus.RUNNING.value)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.id is not None

    v1 = ExperimentVariant(experiment_id=exp.id, name="variant_a", weight=1)
    db_session.add(v1)
    await db_session.flush()
    await db_session.refresh(v1)

    result = await assigner.assign("42", "exp_record", db_session)
    assert result == v1.id


@pytest.mark.asyncio
async def test_assign_returns_none_when_total_weight_zero(db_session):
    assigner = ExperimentAssigner()
    exp = Experiment(name="exp_zero", status=ExperimentStatus.RUNNING.value)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.id is not None

    v1 = ExperimentVariant(experiment_id=exp.id, name="variant_a", weight=0)
    db_session.add(v1)
    await db_session.flush()

    result = await assigner.assign("42", "exp_zero", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_assign_non_numeric_user_id(db_session):
    assigner = ExperimentAssigner()
    exp = Experiment(name="exp_str_user", status=ExperimentStatus.RUNNING.value)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.id is not None

    v1 = ExperimentVariant(experiment_id=exp.id, name="variant_a", weight=1)
    db_session.add(v1)
    await db_session.flush()
    await db_session.refresh(v1)

    result = await assigner.assign("abc", "exp_str_user", db_session)
    assert result == v1.id
