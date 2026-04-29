"""Watchlist endpoints — GET/POST /v1/watchlist, DELETE /v1/watchlist/{ticker}."""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from src.application.services.trading_pipeline import TradingPipelineService
from src.domain.entities.watchlist import WatchlistItem
from src.domain.repositories.watchlist_repository import WatchlistRepository
from src.presentation.auth import require_api_key
from src.presentation.dependencies import TradingContainer

_KST = ZoneInfo("Asia/Seoul")
_MARKET_OPEN = time(9, 0)
_MARKET_CLOSE = time(15, 30)


def _is_market_hours() -> bool:
    now = datetime.now(_KST).time()
    return _MARKET_OPEN <= now <= _MARKET_CLOSE

router = APIRouter(prefix="/v1/watchlist", tags=["watchlist"])


class WatchlistItemResponse(BaseModel):
    ticker: str
    name: str | None
    market: str
    is_active: bool


class AddWatchlistRequest(BaseModel):
    ticker: str = Field(..., pattern=r"^\d{6}$")
    name: str | None = Field(default=None, max_length=100)


def _to_response(item: WatchlistItem) -> WatchlistItemResponse:
    return WatchlistItemResponse(
        ticker=item.ticker,
        name=item.name,
        market=item.market,
        is_active=item.is_active,
    )


@router.get("", response_model=list[WatchlistItemResponse], dependencies=[Depends(require_api_key)])
@inject
async def list_watchlist(
    watchlist_repo: WatchlistRepository = Depends(Provide[TradingContainer.watchlist_repo]),
) -> list[WatchlistItemResponse]:
    items = await watchlist_repo.find_all_active()
    return [_to_response(i) for i in items]


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
@inject
async def add_to_watchlist(
    body: AddWatchlistRequest,
    background_tasks: BackgroundTasks,
    watchlist_repo: WatchlistRepository = Depends(Provide[TradingContainer.watchlist_repo]),
    pipeline: TradingPipelineService = Depends(Provide[TradingContainer.trading_pipeline]),
) -> WatchlistItemResponse:
    item = WatchlistItem(ticker=body.ticker, name=body.name)
    try:
        saved = await watchlist_repo.save(item)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{body.ticker} already in watchlist")

    if _is_market_hours():
        background_tasks.add_task(pipeline.analyze_and_trade_single, body.ticker)

    return _to_response(saved)


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
@inject
async def remove_from_watchlist(
    ticker: str,
    watchlist_repo: WatchlistRepository = Depends(Provide[TradingContainer.watchlist_repo]),
) -> None:
    item = await watchlist_repo.find_by_ticker(ticker)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{ticker} not in watchlist")
    await watchlist_repo.deactivate(ticker)
