import uuid

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.experiment import Experiment, ExperimentStatus, ExperimentVariant
from tests.test_admin_api import create_admin_user, create_regular_user


@pytest.mark.asyncio
async def test_create_experiment(client):
    _admin, token = await create_admin_user()

    response = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"exp_{uuid.uuid4().hex[:8]}",
            "description": "Test experiment",
            "variants": [
                {"name": "control", "weight": 1, "system_prompt": "You are a helpful assistant."},
                {"name": "treatment", "weight": 1, "llm_model": "gpt-4"},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["status"] == ExperimentStatus.DRAFT.value

    async with async_session_maker() as session:
        result = await session.exec(
            select(ExperimentVariant).where(ExperimentVariant.experiment_id == data["id"])
        )
        variants = result.all()
        assert len(variants) == 2


@pytest.mark.asyncio
async def test_create_experiment_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "exp", "variants": []},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_experiments(client):
    _admin, token = await create_admin_user()
    exp_name = f"exp_{uuid.uuid4().hex[:8]}"

    create_resp = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": exp_name, "variants": [{"name": "v1", "weight": 1}]},
    )
    assert create_resp.status_code == 200

    response = await client.get(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    names = [e["name"] for e in data]
    assert exp_name in names


@pytest.mark.asyncio
async def test_list_experiments_with_status_filter(client):
    _admin, token = await create_admin_user()
    exp_name = f"exp_{uuid.uuid4().hex[:8]}"

    create_resp = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": exp_name, "variants": [{"name": "v1", "weight": 1}]},
    )
    assert create_resp.status_code == 200

    response = await client.get(
        f"/api/v1/admin/experiments?status={ExperimentStatus.DRAFT.value}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(e["status"] == ExperimentStatus.DRAFT.value for e in data)
    names = [e["name"] for e in data]
    assert exp_name in names


@pytest.mark.asyncio
async def test_list_experiments_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_experiment(client):
    _admin, token = await create_admin_user()
    create_resp = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"exp_{uuid.uuid4().hex[:8]}", "variants": [{"name": "v1", "weight": 1}]},
    )
    assert create_resp.status_code == 200
    exp_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/v1/admin/experiments/{exp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == exp_id


@pytest.mark.asyncio
async def test_get_experiment_not_found(client):
    _admin, token = await create_admin_user()

    response = await client.get(
        "/api/v1/admin/experiments/999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_experiment_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/experiments/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_start_experiment(client):
    _admin, token = await create_admin_user()
    create_resp = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"exp_{uuid.uuid4().hex[:8]}", "variants": [{"name": "v1", "weight": 1}]},
    )
    assert create_resp.status_code == 200
    exp_id = create_resp.json()["id"]

    response = await client.post(
        f"/api/v1/admin/experiments/{exp_id}/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == ExperimentStatus.RUNNING.value

    async with async_session_maker() as session:
        result = await session.exec(select(Experiment).where(Experiment.id == exp_id))
        exp = result.one()
        assert exp.status == ExperimentStatus.RUNNING.value


@pytest.mark.asyncio
async def test_start_experiment_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.post(
        "/api/v1/admin/experiments/1/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pause_experiment(client):
    _admin, token = await create_admin_user()
    create_resp = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"exp_{uuid.uuid4().hex[:8]}", "variants": [{"name": "v1", "weight": 1}]},
    )
    assert create_resp.status_code == 200
    exp_id = create_resp.json()["id"]

    response = await client.post(
        f"/api/v1/admin/experiments/{exp_id}/pause",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == ExperimentStatus.PAUSED.value

    async with async_session_maker() as session:
        result = await session.exec(select(Experiment).where(Experiment.id == exp_id))
        exp = result.one()
        assert exp.status == ExperimentStatus.PAUSED.value


@pytest.mark.asyncio
async def test_pause_experiment_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.post(
        "/api/v1/admin/experiments/1/pause",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_archive_experiment(client):
    _admin, token = await create_admin_user()
    create_resp = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"exp_{uuid.uuid4().hex[:8]}", "variants": [{"name": "v1", "weight": 1}]},
    )
    assert create_resp.status_code == 200
    exp_id = create_resp.json()["id"]

    response = await client.post(
        f"/api/v1/admin/experiments/{exp_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == ExperimentStatus.COMPLETED.value

    async with async_session_maker() as session:
        result = await session.exec(select(Experiment).where(Experiment.id == exp_id))
        exp = result.one()
        assert exp.status == ExperimentStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_archive_experiment_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.post(
        "/api/v1/admin/experiments/1/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_experiment_results(client):
    _admin, token = await create_admin_user()
    create_resp = await client.post(
        "/api/v1/admin/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"exp_{uuid.uuid4().hex[:8]}", "variants": [{"name": "v1", "weight": 1}]},
    )
    assert create_resp.status_code == 200
    exp_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/v1/admin/experiments/{exp_id}/results",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["variant_name"] == "v1"
    assert data[0]["assignments"] == 0


@pytest.mark.asyncio
async def test_get_experiment_results_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/experiments/1/results",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
