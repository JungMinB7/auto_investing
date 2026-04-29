from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from src.application.ports.audit_port import AuditLogger
from src.application.ports.broker_port import BrokerPort
from src.application.ports.distributed_lock_port import DistributedLock
from src.application.ports.notifier_port import NotifierPort
from src.application.ports.regime_port import MarketRegimePort
from src.application.services.risk_guard import RiskGuardService
from src.domain.entities.signal import SignalType, TradingSignal
from src.domain.entities.trade import OrderSide, OrderType, Trade
from src.domain.exceptions import DuplicateOrderError
from src.domain.repositories.trade_repository import TradeRepository

logger = logging.getLogger(__name__)

_KRX_RE = re.compile(r"^\d{6}$")


def _is_krx(ticker: str) -> bool:
    return bool(_KRX_RE.match(ticker.split()[0].strip()))


def _sizing_factor(trade_score: float) -> float:
    """trade_score → 포지션 크기 배율."""
    if trade_score >= 90:
        return 1.0
    elif trade_score >= 80:
        return 0.7
    return 0.4  # 70-79 zone (notify-only이므로 실제로는 진입 안 함)


@dataclass
class ExecuteTradeRequest:
    ticker: str
    signal: TradingSignal
    trade_score: float = field(default=50.0)


class ExecuteTradeUseCase:
    """신호 → 리스크 검증 → 적응형 포지션 사이징 → 주문 실행 → 감사 로그."""

    def __init__(
        self,
        broker: BrokerPort,
        risk_guard: RiskGuardService,
        trade_repo: TradeRepository,
        lock: DistributedLock,
        audit: AuditLogger,
        notifier: NotifierPort,
        max_position_krw: float,
        max_position_usd: float = 200.0,
        regime: MarketRegimePort | None = None,
    ) -> None:
        self._broker = broker
        self._risk_guard = risk_guard
        self._trade_repo = trade_repo
        self._lock = lock
        self._audit = audit
        self._notifier = notifier
        self._max_position_krw = max_position_krw
        self._max_position_usd = max_position_usd
        self._regime = regime

    async def execute(self, request: ExecuteTradeRequest) -> Trade:
        lock_key = f"trade:{request.ticker}:{date.today().isoformat()}"

        async with self._lock.acquire(lock_key, ttl=300):
            existing = await self._trade_repo.find_by_ticker_today(request.ticker)
            if existing:
                raise DuplicateOrderError(
                    f"Already processed {request.ticker} today ({len(existing)} trade(s) found)"
                )

            current_price = await self._broker.get_current_price(request.ticker)

            quantity = self._calculate_quantity(request.ticker, current_price, request.trade_score)
            if quantity <= 0:
                raise ValueError(
                    f"Cannot calculate valid quantity for {request.ticker}"
                    f" at price={current_price:.4f} score={request.trade_score:.1f}"
                )

            await self._risk_guard.validate(request.ticker, request.signal, quantity, current_price)

            order_side = (
                OrderSide.BUY if request.signal.signal_type == SignalType.BUY else OrderSide.SELL
            )

            broker_order_id = await self._broker.place_order(
                ticker=request.ticker,
                side=order_side,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=current_price,
            )

            trade = Trade(
                ticker=request.ticker,
                order_side=order_side,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=current_price,
                signal_id=request.signal.id,
                kiwoom_order_id=broker_order_id,
            )
            await self._trade_repo.save(trade)

            await self._audit.log(
                event_type="ORDER_PLACED",
                entity_type="trade",
                entity_id=trade.id,
                payload={
                    "ticker": trade.ticker,
                    "side": trade.order_side.value,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "trade_score": request.trade_score,
                    "signal_id": str(trade.signal_id),
                    "broker_order_id": broker_order_id,
                },
            )

            currency = "₩" if _is_krx(request.ticker) else "$"
            await self._notifier.send(
                title=f"주문 실행: {request.ticker}",
                message=(
                    f"{order_side.value} {quantity}주 @ {currency}{current_price:,.2f}\n"
                    f"신호: {request.signal.signal_type.value} "
                    f"({request.signal.confidence.value}) | 점수: {request.trade_score:.0f}점"
                ),
                color=0x2ECC71 if order_side == OrderSide.BUY else 0xE74C3C,
            )

            logger.info(
                "Order placed: %s %s qty=%d price=%.4f score=%.1f order_id=%s",
                request.ticker, order_side.value, quantity, current_price,
                request.trade_score, broker_order_id,
            )
            return trade

    def _calculate_quantity(self, ticker: str, price: float, trade_score: float) -> int:
        if price <= 0:
            return 0

        sf = _sizing_factor(trade_score)
        regime_factor = self._regime.position_factor if self._regime else 1.0
        max_pos = self._max_position_krw if _is_krx(ticker) else self._max_position_usd
        effective = max_pos * sf * regime_factor

        return int(effective / price)
