from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from app.core.limiter import limiter
from app.observability.metrics import record_web_vital

router = APIRouter()


class WebVitalsPayload(BaseModel):
    metric: str = Field(..., pattern="^(LCP|CLS|FID|FCP|TTFB)$")
    value: float = Field(..., ge=0)
    rating: str = Field(..., pattern="^(good|needs-improvement|poor)$")
    url: str = Field(default="", max_length=2048)
    user_agent: str = Field(default="", max_length=512)
    timestamp: str = Field(default="", max_length=64)

    @field_validator("value")
    @classmethod
    def validate_metric_range(cls, v: float, info) -> float:
        metric = info.data.get("metric", "")
        if metric == "LCP" and v > 15:
            raise ValueError("LCP must be <= 15 seconds")
        if metric == "CLS" and v > 1.0:
            raise ValueError("CLS must be <= 1.0")
        if metric == "FID" and v > 5:
            raise ValueError("FID must be <= 5 seconds")
        if metric == "FCP" and v > 15:
            raise ValueError("FCP must be <= 15 seconds")
        if metric == "TTFB" and v > 15:
            raise ValueError("TTFB must be <= 15 seconds")
        return v


class WebVitalsResponse(BaseModel):
    status: str = "recorded"


@router.post(
    "/metrics/web-vitals",
    response_model=WebVitalsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute")
async def receive_web_vitals(
    request: Request,
    response: Response,
    payload: WebVitalsPayload,
) -> WebVitalsResponse:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10240:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large (max 10KB)",
        )

    record_web_vital(payload.metric, payload.value, payload.rating)
    return WebVitalsResponse()
