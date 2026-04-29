"""Signal endpoints — GET /v1/signals/latest, POST /v1/signals/analyze."""
from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from src.application.use_cases.analyze_stock import AnalyzeStockRequest, AnalyzeStockUseCase
from src.domain.repositories.signal_repository import SignalRepository
from src.domain.repositories.watchlist_repository import WatchlistRepository
from src.presentation.auth import require_api_key
from src.presentation.dependencies import TradingContainer
from src.presentation.schemas.signal_schema import AnalyzeRequest, SignalResponse

router = APIRouter(prefix="/v1/signals", tags=["signals"])


def _signal_to_response(sig) -> SignalResponse:
    report = sig.analyst_report or ""
    summary = (report[:200] + "...") if len(report) > 200 else report
    return SignalResponse(
        id=sig.id,
        ticker=sig.ticker,
        signal_type=sig.signal_type,
        confidence=sig.confidence,
        target_price=sig.target_price,
        current_price=sig.current_price,
        report_summary=summary,
        created_at=sig.created_at,
    )


@router.get("/latest", response_model=list[SignalResponse], dependencies=[Depends(require_api_key)])
@inject
async def get_latest_signals(
    watchlist_repo: WatchlistRepository = Depends(Provide[TradingContainer.watchlist_repo]),
    signal_repo: SignalRepository = Depends(Provide[TradingContainer.signal_repo]),
) -> list[SignalResponse]:
    tickers = await watchlist_repo.find_active_tickers()
    results = []
    for ticker in tickers:
        sig = await signal_repo.find_latest(ticker)
        if sig:
            results.append(_signal_to_response(sig))
    return results


@router.post(
    "/analyze",
    response_model=SignalResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
@inject
async def analyze_stock(
    body: AnalyzeRequest,
    analyze_stock_uc: AnalyzeStockUseCase = Depends(Provide[TradingContainer.analyze_stock_uc]),
) -> SignalResponse:
    req = AnalyzeStockRequest(ticker=body.ticker)
    result = await analyze_stock_uc.execute(req)
    if not result.signal:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse signal from broker report",
        )
    return _signal_to_response(result.signal)
