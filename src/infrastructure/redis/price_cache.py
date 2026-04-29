from __future__ import annotations

import redis.asyncio as aioredis

from src.application.ports.price_port import PricePort

_KEY_PREFIX = "price:"


class RedisPriceCacheAdapter(PricePort):
    """Redis 기반 시세 캐시 — 키움 API 호출 최소화."""

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def get_price(self, ticker: str) -> float | None:
        value = await self._client.get(f"{_KEY_PREFIX}{ticker}")
        if value is None:
            return None
        return float(value)

    async def set_price(self, ticker: str, price: float, ttl: int = 60) -> None:
        await self._client.setex(f"{_KEY_PREFIX}{ticker}", ttl, str(price))
