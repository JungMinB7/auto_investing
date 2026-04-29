from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.position import Position
from src.domain.repositories.position_repository import PositionRepository
from src.infrastructure.db.models import PositionModel


def _to_domain(m: PositionModel) -> Position:
    return Position(
        id=m.id,
        ticker=m.ticker,
        quantity=m.quantity,
        avg_cost=float(m.avg_cost),
        realized_pnl=float(m.realized_pnl),
        opened_at=m.opened_at,
        updated_at=m.updated_at,
    )


def _to_model(p: Position) -> PositionModel:
    return PositionModel(
        id=p.id,
        ticker=p.ticker,
        quantity=p.quantity,
        avg_cost=p.avg_cost,
        realized_pnl=p.realized_pnl,
        opened_at=p.opened_at,
        updated_at=p.updated_at,
    )


class PostgresPositionRepository(PositionRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, position: Position) -> Position:
        async with self._sf() as session:
            model = _to_model(position)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def update(self, position: Position) -> Position:
        async with self._sf() as session:
            model = await session.get(PositionModel, position.id)
            if model is None:
                raise ValueError(f"Position {position.id} not found")
            model.quantity = position.quantity
            model.avg_cost = position.avg_cost
            model.realized_pnl = position.realized_pnl
            model.updated_at = position.updated_at
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def find_by_ticker(self, ticker: str) -> Position | None:
        async with self._sf() as session:
            stmt = select(PositionModel).where(PositionModel.ticker == ticker)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return _to_domain(model) if model else None

    async def find_all_active(self) -> list[Position]:
        async with self._sf() as session:
            stmt = select(PositionModel).where(PositionModel.quantity > 0)
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def count_active(self) -> int:
        async with self._sf() as session:
            stmt = select(func.count()).where(PositionModel.quantity > 0)
            result = await session.execute(stmt)
            return result.scalar_one()
