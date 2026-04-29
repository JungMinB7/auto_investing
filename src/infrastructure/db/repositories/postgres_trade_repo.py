from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.trade import OrderSide, OrderStatus, OrderType, Trade
from src.domain.repositories.trade_repository import TradeRepository
from src.infrastructure.db.models import TradeModel


def _to_domain(m: TradeModel) -> Trade:
    return Trade(
        id=m.id,
        ticker=m.ticker,
        order_side=OrderSide(m.order_side),
        order_type=OrderType(m.order_type),
        quantity=m.quantity,
        price=float(m.price) if m.price is not None else None,
        status=OrderStatus(m.status),
        kiwoom_order_id=m.kiwoom_order_id,
        signal_id=m.signal_id,
        filled_price=float(m.filled_price) if m.filled_price is not None else None,
        filled_quantity=m.filled_quantity,
        error_message=m.error_message,
        created_at=m.created_at,
        filled_at=m.filled_at,
    )


def _to_model(t: Trade) -> TradeModel:
    return TradeModel(
        id=t.id,
        ticker=t.ticker,
        order_side=t.order_side.value,
        order_type=t.order_type.value,
        quantity=t.quantity,
        price=t.price,
        status=t.status.value,
        kiwoom_order_id=t.kiwoom_order_id,
        signal_id=t.signal_id,
        filled_price=t.filled_price,
        filled_quantity=t.filled_quantity,
        error_message=t.error_message,
        created_at=t.created_at,
        filled_at=t.filled_at,
    )


class PostgresTradeRepository(TradeRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, trade: Trade) -> Trade:
        async with self._sf() as session:
            model = _to_model(trade)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def update(self, trade: Trade) -> Trade:
        async with self._sf() as session:
            model = await session.get(TradeModel, trade.id)
            if model is None:
                raise ValueError(f"Trade {trade.id} not found")
            model.status = trade.status.value
            model.kiwoom_order_id = trade.kiwoom_order_id
            model.filled_price = trade.filled_price
            model.filled_quantity = trade.filled_quantity
            model.error_message = trade.error_message
            model.filled_at = trade.filled_at
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def find_by_id(self, trade_id: UUID) -> Trade | None:
        async with self._sf() as session:
            model = await session.get(TradeModel, trade_id)
            return _to_domain(model) if model else None

    async def find_by_ticker_today(self, ticker: str) -> list[Trade]:
        today = datetime.now(tz=timezone.utc).date()
        async with self._sf() as session:
            stmt = select(TradeModel).where(
                TradeModel.ticker == ticker,
                TradeModel.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            )
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def find_pending(self) -> list[Trade]:
        async with self._sf() as session:
            stmt = select(TradeModel).where(TradeModel.status == OrderStatus.PENDING.value)
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]
