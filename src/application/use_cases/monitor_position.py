from __future__ import annotations

import logging

from src.application.ports.broker_port import BrokerPort
from src.application.ports.notifier_port import NotifierPort
from src.application.services.risk_guard import RiskGuardService
from src.domain.repositories.position_repository import PositionRepository

logger = logging.getLogger(__name__)

STOP_LOSS_PCT: float = -5.0     # 손절 기준 수익률 (%)
TAKE_PROFIT_PCT: float = 15.0   # 익절 경보 기준 수익률 (%)


class MonitorPositionUseCase:
    """30분마다 활성 포지션 수익률 체크 — 손절/익절 경보."""

    def __init__(
        self,
        position_repo: PositionRepository,
        broker: BrokerPort,
        risk_guard: RiskGuardService,
        notifier: NotifierPort,
    ) -> None:
        self._position_repo = position_repo
        self._broker = broker
        self._risk_guard = risk_guard
        self._notifier = notifier

    async def execute(self) -> None:
        positions = await self._position_repo.find_all_active()
        if not positions:
            logger.debug("No active positions to monitor")
            return

        prices: dict[str, float] = {}
        for position in positions:
            try:
                current_price = await self._broker.get_current_price(position.ticker)
                prices[position.ticker] = current_price
                pnl_pct = position.unrealized_pnl_pct(current_price)
                pnl_krw = position.unrealized_pnl(current_price)

                logger.debug(
                    "Position %s: price=%.0f pnl_pct=%.2f%% pnl_krw=%.0f",
                    position.ticker, current_price, pnl_pct, pnl_krw,
                )

                if pnl_pct <= STOP_LOSS_PCT:
                    logger.warning(
                        "Stop-loss triggered: %s %.2f%% ₩%.0f",
                        position.ticker, pnl_pct, pnl_krw,
                    )
                    await self._notifier.send(
                        title=f"⚠️ 손절 경보: {position.ticker}",
                        message=(
                            f"수익률 {pnl_pct:.1f}%  (₩{pnl_krw:,.0f})\n"
                            f"현재가 ₩{current_price:,.0f} / 평균단가 ₩{position.avg_cost:,.0f}"
                        ),
                        color=0xE74C3C,
                    )

                elif pnl_pct >= TAKE_PROFIT_PCT:
                    logger.info(
                        "Take-profit signal: %s %.2f%% ₩%.0f",
                        position.ticker, pnl_pct, pnl_krw,
                    )
                    await self._notifier.send(
                        title=f"익절 신호: {position.ticker}",
                        message=(
                            f"수익률 {pnl_pct:.1f}%  (₩{pnl_krw:,.0f})\n"
                            f"현재가 ₩{current_price:,.0f} / 익절 검토 권장"
                        ),
                        color=0x2ECC71,
                    )

            except Exception:
                logger.error("Error monitoring position %s", position.ticker, exc_info=True)

        # 포트폴리오 전체 현황 전송 (30분마다)
        await self._notifier.send_portfolio(positions, prices)
