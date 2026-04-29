"""Kiwoom WebSocket client — real-time price feed (Phase 2 skeleton).

Phase 1 scope: Not implemented.
Planned for Phase 2: replace polling-based get_current_price() calls
with a persistent WebSocket subscription during market hours.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class KiwoomWebSocketClient:
    """실시간 시세 구독 WebSocket 클라이언트."""

    async def subscribe_price(self, ticker: str) -> None:
        logger.warning(
            "WebSocket price subscription not yet implemented for %s — using REST polling", ticker
        )

    async def close(self) -> None:
        pass
