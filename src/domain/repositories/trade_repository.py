from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.trade import Trade


class TradeRepository(ABC):
    @abstractmethod
    async def save(self, trade: Trade) -> Trade: ...

    @abstractmethod
    async def update(self, trade: Trade) -> Trade: ...

    @abstractmethod
    async def find_by_id(self, trade_id: UUID) -> Trade | None: ...

    @abstractmethod
    async def find_by_ticker_today(self, ticker: str) -> list[Trade]: ...

    @abstractmethod
    async def find_pending(self) -> list[Trade]: ...
