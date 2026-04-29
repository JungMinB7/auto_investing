from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.position import Position


class PositionRepository(ABC):
    @abstractmethod
    async def save(self, position: Position) -> Position: ...

    @abstractmethod
    async def update(self, position: Position) -> Position: ...

    @abstractmethod
    async def find_by_ticker(self, ticker: str) -> Position | None: ...

    @abstractmethod
    async def find_all_active(self) -> list[Position]: ...

    @abstractmethod
    async def count_active(self) -> int: ...
