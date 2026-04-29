from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.watchlist import WatchlistItem
from src.domain.repositories.watchlist_repository import WatchlistRepository
from src.infrastructure.db.models import WatchlistModel


def _to_domain(m: WatchlistModel) -> WatchlistItem:
    return WatchlistItem(
        id=m.id,
        ticker=m.ticker,
        name=m.name,
        market=m.market,
        is_active=m.is_active,
        added_at=m.added_at,
    )


def _to_model(w: WatchlistItem) -> WatchlistModel:
    return WatchlistModel(
        id=w.id,
        ticker=w.ticker,
        name=w.name,
        market=w.market,
        is_active=w.is_active,
        added_at=w.added_at,
    )


class PostgresWatchlistRepository(WatchlistRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def find_all_active(self) -> list[WatchlistItem]:
        async with self._sf() as session:
            stmt = select(WatchlistModel).where(WatchlistModel.is_active.is_(True))
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def find_active_tickers(self) -> list[str]:
        items = await self.find_all_active()
        return [item.ticker for item in items]

    async def find_by_ticker(self, ticker: str) -> WatchlistItem | None:
        async with self._sf() as session:
            stmt = select(WatchlistModel).where(WatchlistModel.ticker == ticker)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return _to_domain(model) if model else None

    async def save(self, item: WatchlistItem) -> WatchlistItem:
        async with self._sf() as session:
            stmt = select(WatchlistModel).where(WatchlistModel.ticker == item.ticker)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.name = item.name
                existing.is_active = True
                await session.commit()
                await session.refresh(existing)
                return _to_domain(existing)
            model = _to_model(item)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def deactivate(self, ticker: str) -> None:
        async with self._sf() as session:
            stmt = select(WatchlistModel).where(WatchlistModel.ticker == ticker)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                model.is_active = False
                await session.commit()
