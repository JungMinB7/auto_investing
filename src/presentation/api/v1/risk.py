"""Risk management endpoints — GET /v1/risk/status, POST /v1/risk/resume."""
from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.application.services.risk_guard import RiskGuardService
from src.domain.repositories.position_repository import PositionRepository
from src.presentation.auth import require_api_key
from src.presentation.dependencies import TradingContainer

router = APIRouter(prefix="/v1/risk", tags=["risk"])


class RiskStatusResponse(BaseModel):
    trading_halted: bool
    daily_loss_krw: float
    open_position_count: int
    halt_reason: str | None


@router.get("/status", response_model=RiskStatusResponse, dependencies=[Depends(require_api_key)])
@inject
async def get_risk_status(
    risk_guard: RiskGuardService = Depends(Provide[TradingContainer.risk_guard]),
    position_repo: PositionRepository = Depends(Provide[TradingContainer.position_repo]),
) -> RiskStatusResponse:
    snapshot = await risk_guard.get_today_snapshot()
    count = await position_repo.count_active()
    return RiskStatusResponse(
        trading_halted=snapshot.trading_halted,
        daily_loss_krw=snapshot.daily_loss,
        open_position_count=count,
        halt_reason=snapshot.halt_reason,
    )


@router.post("/resume", dependencies=[Depends(require_api_key)])
@inject
async def resume_trading(
    risk_guard: RiskGuardService = Depends(Provide[TradingContainer.risk_guard]),
) -> dict:
    await risk_guard.resume_trading()
    return {"status": "resumed"}
