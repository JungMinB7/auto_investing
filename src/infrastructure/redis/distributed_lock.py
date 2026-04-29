from __future__ import annotations

import redis.asyncio as aioredis

from src.application.ports.distributed_lock_port import DistributedLock
from src.domain.exceptions import LockAcquisitionError


class _LockContext:
    """Redis SET NX EX 기반 분산 락 컨텍스트 매니저."""

    def __init__(self, client: aioredis.Redis, key: str, ttl: int) -> None:
        self._client = client
        self._key = key
        self._ttl = ttl

    async def __aenter__(self) -> None:
        acquired = await self._client.set(self._key, "1", nx=True, ex=self._ttl)
        if not acquired:
            raise LockAcquisitionError(
                f"Could not acquire distributed lock for key='{self._key}' "
                f"— concurrent operation in progress"
            )

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._client.delete(self._key)


class RedisDistributedLock(DistributedLock):
    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    def acquire(self, key: str, ttl: int = 300) -> _LockContext:
        return _LockContext(self._client, key, ttl)
