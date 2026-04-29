"""Scheduler control endpoints — POST /v1/scheduler/start|stop."""
from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.infrastructure.scheduler.trading_scheduler import TradingScheduler
from src.presentation.auth import require_api_key
from src.presentation.dependencies import TradingContainer

router = APIRouter(prefix="/v1/scheduler", tags=["scheduler"])


class SchedulerStatusResponse(BaseModel):
    running: bool


@router.post("/start", response_model=SchedulerStatusResponse, dependencies=[Depends(require_api_key)])
@inject
async def start_scheduler(
    scheduler: TradingScheduler = Depends(Provide[TradingContainer.scheduler]),
) -> SchedulerStatusResponse:
    if not scheduler.running:
        scheduler.start()
    return SchedulerStatusResponse(running=scheduler.running)


@router.post("/stop", response_model=SchedulerStatusResponse, dependencies=[Depends(require_api_key)])
@inject
async def stop_scheduler(
    scheduler: TradingScheduler = Depends(Provide[TradingContainer.scheduler]),
) -> SchedulerStatusResponse:
    scheduler.shutdown(wait=False)
    return SchedulerStatusResponse(running=scheduler.running)
