import logging
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.models.experiment import ExperimentStatus
from app.services.experiment import ExperimentService
from app.services.experiment_assigner import ExperimentAssigner

router = APIRouter()
logger = logging.getLogger(__name__)
experiment_service = ExperimentService()
experiment_assigner = ExperimentAssigner()


class VariantCreateRequest(BaseModel):
    name: str
    weight: int = 1
    system_prompt: str | None = None
    llm_model: str | None = None
    retriever_top_k: int | None = None
    reranker_enabled: bool | None = None
    extra_config: dict[str, Any] | None = None


class ExperimentCreateRequest(BaseModel):
    name: str
    description: str | None = None
    variants: list[VariantCreateRequest]


class ExperimentResponse(BaseModel):
    id: int
    name: str
    description: str | None
    status: str
    created_at: str
    updated_at: str


class ExperimentResultItem(BaseModel):
    variant_id: int
    variant_name: str
    weight: int
    assignments: int


@router.post("", response_model=ExperimentResponse)
async def create_experiment(
    request: ExperimentCreateRequest,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    exp = await experiment_service.create_experiment(
        db=session,
        name=request.name,
        description=request.description,
        variants=[v.model_dump() for v in request.variants],
    )
    return ExperimentResponse(
        id=cast(int, exp.id),
        name=exp.name,
        description=exp.description,
        status=exp.status,
        created_at=exp.created_at.isoformat() if exp.created_at else "",
        updated_at=exp.updated_at.isoformat() if exp.updated_at else "",
    )


@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    experiments = await experiment_service.list_experiments(
        db=session, status=status, offset=offset, limit=limit
    )
    return [
        ExperimentResponse(
            id=cast(int, e.id),
            name=e.name,
            description=e.description,
            status=e.status,
            created_at=e.created_at.isoformat() if e.created_at else "",
            updated_at=e.updated_at.isoformat() if e.updated_at else "",
        )
        for e in experiments
    ]


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: int,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    exp = await experiment_service.get_experiment(db=session, experiment_id=experiment_id)
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return ExperimentResponse(
        id=cast(int, exp.id),
        name=exp.name,
        description=exp.description,
        status=exp.status,
        created_at=exp.created_at.isoformat() if exp.created_at else "",
        updated_at=exp.updated_at.isoformat() if exp.updated_at else "",
    )


@router.post("/{experiment_id}/start")
async def start_experiment(
    experiment_id: int,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    ok = await experiment_service.set_status(
        db=session, experiment_id=experiment_id, status=ExperimentStatus.RUNNING.value
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return {
        "success": True,
        "experiment_id": experiment_id,
        "status": ExperimentStatus.RUNNING.value,
    }


@router.post("/{experiment_id}/pause")
async def pause_experiment(
    experiment_id: int,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    ok = await experiment_service.set_status(
        db=session, experiment_id=experiment_id, status=ExperimentStatus.PAUSED.value
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return {
        "success": True,
        "experiment_id": experiment_id,
        "status": ExperimentStatus.PAUSED.value,
    }


@router.post("/{experiment_id}/archive")
async def archive_experiment(
    experiment_id: int,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    ok = await experiment_service.set_status(
        db=session, experiment_id=experiment_id, status=ExperimentStatus.COMPLETED.value
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return {
        "success": True,
        "experiment_id": experiment_id,
        "status": ExperimentStatus.COMPLETED.value,
    }


@router.get("/{experiment_id}/results", response_model=list[ExperimentResultItem])
async def get_experiment_results(
    experiment_id: int,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    exp = await experiment_service.get_experiment(db=session, experiment_id=experiment_id)
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    results = await experiment_service.get_results(db=session, experiment_id=experiment_id)
    return [ExperimentResultItem(**r) for r in results]
