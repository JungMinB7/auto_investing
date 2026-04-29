from __future__ import annotations

from abc import ABC, abstractmethod


class PricePort(ABC):
    """Redis 기반 시세 캐시 포트 — 외부 API 호출 최소화."""

    @abstractmethod
    async def get_price(self, ticker: str) -> float | None: ...

    @abstractmethod
    async def set_price(self, ticker: str, price: float, ttl: int = 60) -> None: ...
