import pytest

from app.models.experiment import Experiment, ExperimentStatus, ExperimentVariant
from app.models.user import User
from app.services.experiment_assigner import (
    ExperimentAssigner,
    VariantConfig,
    _deterministic_hash,
)


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


@pytest.mark.asyncio
async def test_assign_with_config_returns_none_when_experiment_not_found(db_session):
    assigner = ExperimentAssigner()
    result = await assigner.assign_with_config("123", "nonexistent_exp", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_assign_with_config_returns_full_variant_config(db_session):
    user = User(
        username="exp_test_user1",
        password_hash=User.hash_password("testpass"),
        email="exp1@test.com",
        full_name="Exp Test User 1",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    assigner = ExperimentAssigner()
    exp = Experiment(name="exp_config", status=ExperimentStatus.RUNNING.value)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.id is not None

    v1 = ExperimentVariant(
        experiment_id=exp.id,
        name="variant_config",
        weight=1,
        system_prompt="test prompt",
        llm_model="gpt-4o-mini",
        retriever_top_k=8,
        reranker_enabled=False,
        memory_context_config={"memory_token_budget": 512},
        extra_config={"temperature": 0.5},
    )
    db_session.add(v1)
    await db_session.flush()
    await db_session.refresh(v1)
    assert v1.id is not None

    result = await assigner.assign_with_config(str(user.id), "exp_config", db_session)
    assert isinstance(result, VariantConfig)
    assert result.variant_id == v1.id
    assert result.system_prompt == "test prompt"
    assert result.llm_model == "gpt-4o-mini"
    assert result.retriever_top_k == 8
    assert result.reranker_enabled is False
    assert result.memory_context_config == {"memory_token_budget": 512}
    assert result.extra_config == {"temperature": 0.5}


@pytest.mark.asyncio
async def test_variant_config_defaults_none(db_session):
    user = User(
        username="exp_test_user2",
        password_hash=User.hash_password("testpass"),
        email="exp2@test.com",
        full_name="Exp Test User 2",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    assigner = ExperimentAssigner()
    exp = Experiment(name="exp_defaults", status=ExperimentStatus.RUNNING.value)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.id is not None

    v1 = ExperimentVariant(experiment_id=exp.id, name="variant_defaults", weight=1)
    db_session.add(v1)
    await db_session.flush()
    await db_session.refresh(v1)
    assert v1.id is not None

    result = await assigner.assign_with_config(str(user.id), "exp_defaults", db_session)
    assert isinstance(result, VariantConfig)
    assert result.variant_id == v1.id
    assert result.system_prompt is None
    assert result.llm_model is None
    assert result.retriever_top_k is None
    assert result.reranker_enabled is None
    assert result.memory_context_config is None
    assert result.extra_config is None
