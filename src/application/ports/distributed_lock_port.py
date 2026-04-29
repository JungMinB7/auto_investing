from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager


class DistributedLock(ABC):
    """Redis 분산 락 포트 — 중복 주문 방지를 위한 ticker-date 레벨 락."""

    @abstractmethod
    def acquire(self, key: str, ttl: int = 300) -> AbstractAsyncContextManager[None]:
        """async with lock.acquire(key) 형태로 사용."""
        ...
