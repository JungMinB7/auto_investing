from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.watchlist import WatchlistItem


class WatchlistRepository(ABC):
    @abstractmethod
    async def find_all_active(self) -> list[WatchlistItem]: ...

    @abstractmethod
    async def find_active_tickers(self) -> list[str]: ...

    @abstractmethod
    async def find_by_ticker(self, ticker: str) -> WatchlistItem | None: ...

    @abstractmethod
    async def save(self, item: WatchlistItem) -> WatchlistItem: ...

    @abstractmethod
    async def deactivate(self, ticker: str) -> None: ...
