from __future__ import annotations

import logging

from src.domain.entities.risk_rule import RiskRule
from src.domain.entities.risk_snapshot import RiskSnapshot
from src.domain.entities.signal import TradingSignal
from src.domain.exceptions import (
    DailyLossLimitError,
    LowConfidenceError,
    PositionLimitError,
    PositionSizeError,
    TradingHaltedError,
)
from src.domain.repositories.position_repository import PositionRepository
from src.domain.repositories.risk_snapshot_repository import RiskSnapshotRepository

logger = logging.getLogger(__name__)


class RiskGuardService:
    """5-rule 리스크 검증 서비스. 검증 실패 시 예외 발생 — fail-safe 설계."""

    def __init__(
        self,
        rule: RiskRule,
        position_repo: PositionRepository,
        snapshot_repo: RiskSnapshotRepository,
    ) -> None:
        self._rule = rule
        self._position_repo = position_repo
        self._snapshot_repo = snapshot_repo

    async def validate(
        self,
        ticker: str,
        signal: TradingSignal,
        quantity: int,
        price: float,
    ) -> None:
        """모든 리스크 규칙 검증. 예외 없으면 주문 가능."""
        snapshot = await self._snapshot_repo.get_or_create_today()

        # Rule 1: 거래 중단 여부
        if snapshot.trading_halted:
            raise TradingHaltedError(f"Trading halted: {snapshot.halt_reason}")

        # Rule 2: 일일 손실 한도
        if snapshot.daily_loss >= self._rule.max_daily_loss_krw:
            await self._do_halt(snapshot, "일일 손실 한도 초과")
            raise DailyLossLimitError(
                f"Daily loss limit reached: ₩{snapshot.daily_loss:,.0f}"
                f" / ₩{self._rule.max_daily_loss_krw:,.0f}"
            )

        # Rule 3: 최대 포지션 수
        position_count = await self._position_repo.count_active()
        if position_count >= self._rule.max_position_count:
            raise PositionLimitError(
                f"Max positions reached: {position_count}/{self._rule.max_position_count}"
            )

        # Rule 4: 종목당 최대 투자금액
        investment_krw = quantity * price
        if investment_krw > self._rule.max_position_krw:
            raise PositionSizeError(
                f"Investment ₩{investment_krw:,.0f}"
                f" exceeds max ₩{self._rule.max_position_krw:,.0f}"
            )

        # Rule 5: 최소 신뢰도
        if not signal.confidence.meets_minimum(self._rule.min_signal_confidence):
            raise LowConfidenceError(
                f"Signal confidence {signal.confidence.value}"
                f" below minimum {self._rule.min_signal_confidence.value}"
            )

    async def record_pnl(self, pnl: float) -> None:
        """포지션 PnL 기록. 손실 한도 초과 시 자동 거래 중단."""
        snapshot = await self._snapshot_repo.get_or_create_today()
        snapshot.add_pnl(pnl)
        await self._snapshot_repo.update(snapshot)

        if snapshot.daily_loss >= self._rule.max_daily_loss_krw and not snapshot.trading_halted:
            await self._do_halt(snapshot, "일일 손실 한도 초과 (자동 중단)")
            logger.warning(
                "Trading auto-halted: daily_loss=₩%.0f limit=₩%.0f",
                snapshot.daily_loss,
                self._rule.max_daily_loss_krw,
            )

    async def resume_trading(self) -> None:
        """수동으로 거래 중단 해제 (FastAPI /v1/risk/resume 엔드포인트에서 호출)."""
        snapshot = await self._snapshot_repo.get_or_create_today()
        snapshot.resume()
        await self._snapshot_repo.update(snapshot)
        logger.info("Trading resumed manually")

    async def get_today_snapshot(self) -> RiskSnapshot:
        return await self._snapshot_repo.get_or_create_today()

    async def _do_halt(self, snapshot: RiskSnapshot, reason: str) -> None:
        snapshot.halt(reason)
        await self._snapshot_repo.update(snapshot)
        logger.warning("Trading halted: %s", reason)
