from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.risk_snapshot import RiskSnapshot
from src.domain.repositories.risk_snapshot_repository import RiskSnapshotRepository
from src.infrastructure.db.models import RiskSnapshotModel


def _to_domain(m: RiskSnapshotModel) -> RiskSnapshot:
    return RiskSnapshot(
        id=m.id,
        snapshot_date=m.snapshot_date,
        daily_pnl=float(m.daily_pnl),
        daily_loss=float(m.daily_loss),
        trading_halted=m.trading_halted,
        halt_reason=m.halt_reason,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_model(s: RiskSnapshot) -> RiskSnapshotModel:
    return RiskSnapshotModel(
        id=s.id,
        snapshot_date=s.snapshot_date,
        daily_pnl=s.daily_pnl,
        daily_loss=s.daily_loss,
        trading_halted=s.trading_halted,
        halt_reason=s.halt_reason,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


class PostgresRiskSnapshotRepository(RiskSnapshotRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def find_by_date(self, snapshot_date: date) -> RiskSnapshot | None:
        async with self._sf() as session:
            stmt = select(RiskSnapshotModel).where(
                RiskSnapshotModel.snapshot_date == snapshot_date
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return _to_domain(model) if model else None

    async def find_today(self) -> RiskSnapshot | None:
        return await self.find_by_date(datetime.now(tz=timezone.utc).date())

    async def get_or_create_today(self) -> RiskSnapshot:
        today = datetime.now(tz=timezone.utc).date()
        existing = await self.find_by_date(today)
        if existing:
            return existing
        new_snapshot = RiskSnapshot(snapshot_date=today)
        return await self.save(new_snapshot)

    async def save(self, snapshot: RiskSnapshot) -> RiskSnapshot:
        async with self._sf() as session:
            model = _to_model(snapshot)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def update(self, snapshot: RiskSnapshot) -> RiskSnapshot:
        async with self._sf() as session:
            model = await session.get(RiskSnapshotModel, snapshot.id)
            if model is None:
                raise ValueError(f"RiskSnapshot {snapshot.id} not found")
            model.daily_pnl = snapshot.daily_pnl
            model.daily_loss = snapshot.daily_loss
            model.trading_halted = snapshot.trading_halted
            model.halt_reason = snapshot.halt_reason
            model.updated_at = snapshot.updated_at
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)
