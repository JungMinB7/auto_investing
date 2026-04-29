from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.entities.position import Position
    from src.domain.entities.signal import TradingSignal


class NotifierPort(ABC):
    @abstractmethod
    async def send(self, title: str, message: str, color: int = 0x00FF00) -> None: ...

    async def send_report(self, ticker: str, signal: "TradingSignal", raw_report: str) -> None:
        """분석 리포트 Discord 전송 — 기본 구현은 단순 텍스트."""
        await self.send(
            title=f"📊 {ticker} 분석 완료",
            message=f"의견: {signal.signal_type.value} | 신뢰도: {signal.confidence.value}",
        )

    async def send_portfolio(self, positions: list["Position"], prices: dict[str, float]) -> None:
        """포트폴리오 현황 Discord 전송 — 기본 구현은 단순 텍스트."""
        if not positions:
            return
        lines = [f"{p.ticker}: {p.unrealized_pnl_pct(prices.get(p.ticker, p.avg_cost)):.1f}%" for p in positions]
        await self.send(title="📈 포트폴리오 현황", message="\n".join(lines))
