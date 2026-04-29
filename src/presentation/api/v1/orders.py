"""Order endpoints — GET /v1/orders, POST /v1/orders."""
from __future__ import annotations

import uuid
from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from src.application.ports.broker_port import BrokerPort
from src.domain.entities.trade import OrderStatus, Trade
from src.domain.repositories.trade_repository import TradeRepository
from src.presentation.auth import require_api_key
from src.presentation.dependencies import TradingContainer
from src.presentation.schemas.order_schema import ManualOrderRequest, TradeResponse

router = APIRouter(prefix="/v1/orders", tags=["orders"])


def _trade_to_response(trade: Trade) -> TradeResponse:
    return TradeResponse(
        id=trade.id,
        ticker=trade.ticker,
        side=trade.order_side,
        order_type=trade.order_type,
        quantity=trade.quantity,
        price=trade.price,
        status=trade.status,
        order_id=trade.kiwoom_order_id,
        created_at=trade.created_at,
    )


@router.get("", response_model=list[TradeResponse], dependencies=[Depends(require_api_key)])
@inject
async def list_orders(
    trade_repo: TradeRepository = Depends(Provide[TradingContainer.trade_repo]),
) -> list[TradeResponse]:
    trades = await trade_repo.find_pending()
    return [_trade_to_response(t) for t in trades]


@router.post(
    "",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
@inject
async def place_manual_order(
    body: ManualOrderRequest,
    broker: BrokerPort = Depends(Provide[TradingContainer.kiwoom]),
    trade_repo: TradeRepository = Depends(Provide[TradingContainer.trade_repo]),
) -> TradeResponse:
    order_id = await broker.place_order(
        ticker=body.ticker,
        side=body.side,
        order_type=body.order_type,
        quantity=body.quantity,
        price=body.price,
    )
    trade = Trade(
        id=uuid.uuid4(),
        ticker=body.ticker,
        order_side=body.side,
        order_type=body.order_type,
        quantity=body.quantity,
        price=body.price,
        status=OrderStatus.PENDING,
        kiwoom_order_id=order_id,
        created_at=datetime.utcnow(),
    )
    await trade_repo.save(trade)
    return _trade_to_response(trade)
