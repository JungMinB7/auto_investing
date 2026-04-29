"""GET /v1/positions — active position endpoints."""
from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from src.domain.repositories.position_repository import PositionRepository
from src.presentation.auth import require_api_key
from src.presentation.dependencies import TradingContainer
from src.presentation.schemas.position_schema import PositionResponse

router = APIRouter(prefix="/v1/positions", tags=["positions"])


def _to_response(pos) -> PositionResponse:
    avg_cost = float(pos.avg_cost)
    current_price = avg_cost  # default; live price requires broker call
    pnl = (current_price - avg_cost) * pos.quantity
    pnl_pct = 0.0
    return PositionResponse(
        id=pos.id,
        ticker=pos.ticker,
        quantity=pos.quantity,
        avg_cost=avg_cost,
        current_price=current_price,
        unrealized_pnl=pnl,
        unrealized_pnl_pct=pnl_pct,
        opened_at=pos.opened_at,
    )


@router.get("", response_model=list[PositionResponse], dependencies=[Depends(require_api_key)])
@inject
async def get_positions(
    position_repo: PositionRepository = Depends(Provide[TradingContainer.position_repo]),
) -> list[PositionResponse]:
    positions = await position_repo.find_all_active()
    return [_to_response(p) for p in positions]


@router.get("/{ticker}", response_model=PositionResponse, dependencies=[Depends(require_api_key)])
@inject
async def get_position(
    ticker: str,
    position_repo: PositionRepository = Depends(Provide[TradingContainer.position_repo]),
) -> PositionResponse:
    pos = await position_repo.find_by_ticker(ticker)
    if pos is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active position for {ticker}")
    return _to_response(pos)
