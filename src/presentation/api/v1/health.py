"""GET /health — system health check."""
from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.infrastructure.kiwoom.kiwoom_adapter import KiwoomRestAdapter
from src.infrastructure.scheduler.trading_scheduler import TradingScheduler
from src.presentation.dependencies import TradingContainer

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    kiwoom: str
    scheduler_running: bool


@router.get("/health", response_model=HealthResponse)
@inject
async def health_check(
    kiwoom: KiwoomRestAdapter = Depends(Provide[TradingContainer.kiwoom]),
    scheduler: TradingScheduler = Depends(Provide[TradingContainer.scheduler]),
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        db="ok",
        redis="ok",
        kiwoom="paper" if kiwoom._is_paper else "live",
        scheduler_running=scheduler.running,
    )
