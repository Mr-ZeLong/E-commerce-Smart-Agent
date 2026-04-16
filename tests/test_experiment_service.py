import pytest

from app.models.experiment import ExperimentStatus
from app.services.experiment import ExperimentService


@pytest.fixture
def experiment_service() -> ExperimentService:
    return ExperimentService()


@pytest.mark.asyncio
async def test_create_experiment(experiment_service: ExperimentService, db_session):
    exp = await experiment_service.create_experiment(
        db_session,
        name="test_exp",
        description="A test experiment",
        variants=[
            {"name": "control", "weight": 1},
            {"name": "treatment", "weight": 2, "system_prompt": "prompt"},
        ],
    )
    assert exp.id is not None
    assert exp.name == "test_exp"
    assert exp.status == ExperimentStatus.DRAFT.value

    variants = await experiment_service.get_variants(db_session, exp.id)
    assert len(variants) == 2
    assert {v.name for v in variants} == {"control", "treatment"}


@pytest.mark.asyncio
async def test_get_experiment(experiment_service: ExperimentService, db_session):
    exp = await experiment_service.create_experiment(
        db_session, name="get_me", description=None, variants=[{"name": "v1"}]
    )
    assert exp.id is not None
    fetched = await experiment_service.get_experiment(db_session, exp.id)
    assert fetched is not None
    assert fetched.name == "get_me"


@pytest.mark.asyncio
async def test_get_experiment_returns_none_for_missing(
    experiment_service: ExperimentService, db_session
):
    result = await experiment_service.get_experiment(db_session, 99999)
    assert result is None


@pytest.mark.asyncio
async def test_list_experiments_filters_by_status(
    experiment_service: ExperimentService, db_session
):
    await experiment_service.create_experiment(
        db_session, name="draft_exp", description=None, variants=[{"name": "v1"}]
    )
    running_exp = await experiment_service.create_experiment(
        db_session, name="running_exp", description=None, variants=[{"name": "v1"}]
    )
    running_exp.status = ExperimentStatus.RUNNING.value
    db_session.add(running_exp)
    await db_session.commit()

    drafts = await experiment_service.list_experiments(
        db_session, status=ExperimentStatus.DRAFT.value
    )
    assert all(e.status == ExperimentStatus.DRAFT.value for e in drafts)

    running = await experiment_service.list_experiments(
        db_session, status=ExperimentStatus.RUNNING.value
    )
    assert len(running) >= 1
    assert running[0].name == "running_exp"


@pytest.mark.asyncio
async def test_set_status(experiment_service: ExperimentService, db_session):
    exp = await experiment_service.create_experiment(
        db_session, name="status_exp", description=None, variants=[{"name": "v1"}]
    )
    assert exp.id is not None
    success = await experiment_service.set_status(
        db_session, exp.id, ExperimentStatus.RUNNING.value
    )
    assert success is True

    fetched = await experiment_service.get_experiment(db_session, exp.id)
    assert fetched is not None
    assert fetched.status == ExperimentStatus.RUNNING.value


@pytest.mark.asyncio
async def test_set_status_missing_experiment(experiment_service: ExperimentService, db_session):
    success = await experiment_service.set_status(db_session, 99999, ExperimentStatus.RUNNING.value)
    assert success is False


@pytest.mark.asyncio
async def test_get_results_counts_assignments(experiment_service: ExperimentService, db_session):
    exp = await experiment_service.create_experiment(
        db_session,
        name="results_exp",
        description=None,
        variants=[{"name": "a", "weight": 1}, {"name": "b", "weight": 1}],
    )
    assert exp.id is not None
    variants = await experiment_service.get_variants(db_session, exp.id)
    assert len(variants) == 2

    results = await experiment_service.get_results(db_session, exp.id)
    assert len(results) == 2
    for r in results:
        assert r["assignments"] == 0
        assert "variant_id" in r
        assert "variant_name" in r
        assert "weight" in r


@pytest.mark.asyncio
async def test_list_experiments_pagination(experiment_service: ExperimentService, db_session):
    for i in range(5):
        await experiment_service.create_experiment(
            db_session, name=f"paginated_{i}", description=None, variants=[{"name": "v1"}]
        )
    page = await experiment_service.list_experiments(db_session, offset=0, limit=2)
    assert len(page) == 2
