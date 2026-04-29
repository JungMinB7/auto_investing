from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.signal import ConfidenceLevel, SignalType, TradingSignal
from src.domain.repositories.signal_repository import SignalRepository
from src.infrastructure.db.models import SignalModel


def _to_domain(m: SignalModel) -> TradingSignal:
    return TradingSignal(
        id=m.id,
        ticker=m.ticker,
        signal_type=SignalType(m.signal_type),
        confidence=ConfidenceLevel.from_string(m.confidence),
        target_price=float(m.target_price) if m.target_price is not None else None,
        current_price=float(m.current_price) if m.current_price is not None else None,
        upside_pct=float(m.upside_pct) if m.upside_pct is not None else None,
        analyst_report=m.analyst_report or "",
        created_at=m.created_at,
    )


def _to_model(s: TradingSignal) -> SignalModel:
    return SignalModel(
        id=s.id,
        ticker=s.ticker,
        signal_type=s.signal_type.value,
        confidence=s.confidence.value,
        target_price=s.target_price,
        current_price=s.current_price,
        upside_pct=s.upside_pct,
        analyst_report=s.analyst_report,
        created_at=s.created_at,
    )


class PostgresSignalRepository(SignalRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, signal: TradingSignal) -> TradingSignal:
        async with self._sf() as session:
            model = _to_model(signal)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def find_by_id(self, signal_id: UUID) -> TradingSignal | None:
        async with self._sf() as session:
            model = await session.get(SignalModel, signal_id)
            return _to_domain(model) if model else None

    async def find_by_ticker_today(self, ticker: str) -> list[TradingSignal]:
        today = datetime.now(tz=timezone.utc).date()
        async with self._sf() as session:
            stmt = select(SignalModel).where(
                SignalModel.ticker == ticker,
                SignalModel.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            ).order_by(SignalModel.created_at.desc())
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def find_latest(self, limit: int = 20) -> list[TradingSignal]:
        async with self._sf() as session:
            stmt = (
                select(SignalModel)
                .order_by(SignalModel.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]
