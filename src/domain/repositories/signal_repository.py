from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.signal import TradingSignal


class SignalRepository(ABC):
    @abstractmethod
    async def save(self, signal: TradingSignal) -> TradingSignal: ...

    @abstractmethod
    async def find_by_id(self, signal_id: UUID) -> TradingSignal | None: ...

    @abstractmethod
    async def find_by_ticker_today(self, ticker: str) -> list[TradingSignal]: ...

    @abstractmethod
    async def find_latest(self, limit: int = 20) -> list[TradingSignal]: ...
