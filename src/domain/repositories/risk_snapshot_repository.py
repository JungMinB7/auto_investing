from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from src.domain.entities.risk_snapshot import RiskSnapshot


class RiskSnapshotRepository(ABC):
    @abstractmethod
    async def find_by_date(self, snapshot_date: date) -> RiskSnapshot | None: ...

    @abstractmethod
    async def find_today(self) -> RiskSnapshot | None: ...

    @abstractmethod
    async def get_or_create_today(self) -> RiskSnapshot: ...

    @abstractmethod
    async def save(self, snapshot: RiskSnapshot) -> RiskSnapshot: ...

    @abstractmethod
    async def update(self, snapshot: RiskSnapshot) -> RiskSnapshot: ...
